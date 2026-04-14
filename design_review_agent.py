"""
Binocs Design Review Agent — Standalone Runner

Reviews Figma designs against Binocs UI/UX standards using the Anthropic API
and Figma REST API. This is the automation alternative to using Claude Code directly.

Prerequisites:
    export ANTHROPIC_API_KEY="your-anthropic-key"
    export FIGMA_ACCESS_TOKEN="your-figma-personal-access-token"

Usage:
    # Review all frames on a Figma page
    python design_review_agent.py "https://www.figma.com/design/FILE_KEY/Name?node-id=PAGE_ID"

    # Review with output file
    python design_review_agent.py "https://www.figma.com/design/FILE_KEY/Name?node-id=PAGE_ID" --output review.txt

    # Review specific frames only
    python design_review_agent.py "https://www.figma.com/design/FILE_KEY/Name?node-id=PAGE_ID" --frames "Frame 1,Frame 2,Frame 3"

    # Post comments to Figma
    python design_review_agent.py "https://www.figma.com/design/FILE_KEY/Name?node-id=PAGE_ID" --comment
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import anthropic
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SKILL_PATH = Path(__file__).parent / ".claude" / "skills" / "design-review" / "SKILL.md"
FIGMA_API_BASE = "https://api.figma.com/v1"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384
BATCH_SIZE = 6  # Frames per review batch
MAX_RETRIES = 2  # Retry count for transient API errors


# ---------------------------------------------------------------------------
# Figma API Client
# ---------------------------------------------------------------------------

class FigmaClient:
    """Lightweight Figma REST API client for design data retrieval."""

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"X-Figma-Token": token})

    def get_file(self, file_key: str) -> dict:
        """Get full file metadata."""
        resp = self.session.get(f"{FIGMA_API_BASE}/files/{file_key}")
        resp.raise_for_status()
        return resp.json()

    def get_file_nodes(self, file_key: str, node_ids: list[str]) -> dict:
        """Get specific nodes with full layout data."""
        ids = ",".join(node_ids)
        resp = self.session.get(
            f"{FIGMA_API_BASE}/files/{file_key}/nodes",
            params={"ids": ids, "geometry": "paths"},
        )
        resp.raise_for_status()
        return resp.json()

    def get_images(
        self, file_key: str, node_ids: list[str], scale: float = 2.0, fmt: str = "png"
    ) -> dict[str, str]:
        """Get rendered images (URLs) for specific nodes."""
        ids = ",".join(node_ids)
        resp = self.session.get(
            f"{FIGMA_API_BASE}/images/{file_key}",
            params={"ids": ids, "scale": scale, "format": fmt},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("images", {})

    def post_comment(
        self, file_key: str, message: str, node_id: str | None = None,
        x: float | None = None, y: float | None = None,
    ) -> dict:
        """Post a comment to a Figma file, optionally pinned to a node/position."""
        body = {"message": message}
        if node_id:
            # Pin comment to a specific node
            body["client_meta"] = {"node_id": node_id}
            if x is not None and y is not None:
                body["client_meta"]["node_offset"] = {"x": x, "y": y}
        resp = self.session.post(
            f"{FIGMA_API_BASE}/files/{file_key}/comments",
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    def download_image(self, url: str) -> bytes:
        """Download a rendered image from Figma's CDN."""
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.content


# ---------------------------------------------------------------------------
# Figma URL Parsing
# ---------------------------------------------------------------------------

def parse_figma_url(url: str) -> tuple[str, str | None]:
    """
    Extract file_key and node_id from a Figma URL.
    Returns (file_key, node_id_or_none).
    """
    file_key = None
    node_id = None

    # Handle /design/ and /file/ URL formats
    pattern = r"figma\.com/(?:design|file)/([a-zA-Z0-9]+)"
    match = re.search(pattern, url)
    if match:
        file_key = match.group(1)

    # Extract node-id parameter
    node_pattern = r"node-id=([^&]+)"
    node_match = re.search(node_pattern, url)
    if node_match:
        node_id = unquote(node_match.group(1))

    if not file_key:
        print(f"Error: Could not extract file key from URL: {url}", file=sys.stderr)
        sys.exit(1)

    return file_key, node_id


def discover_frames(figma: FigmaClient, file_key: str, page_node_id: str | None) -> list[dict]:
    """
    Discover all top-level frames on a page.
    Returns list of {id, name, type} dicts sorted by x-position.
    """
    file_data = figma.get_file(file_key)
    document = file_data.get("document", {})

    # Find the target page
    pages = document.get("children", [])
    target_page = None

    if page_node_id:
        # Find page containing this node ID — node_id format: "123:456"
        # Page-level node IDs are the direct children of the document
        for page in pages:
            if page["id"] == page_node_id:
                target_page = page
                break
            # Also check if the node_id refers to a child within this page
            for child in page.get("children", []):
                if child["id"] == page_node_id:
                    target_page = page
                    break
            if target_page:
                break

    if not target_page:
        # Default to first page
        if pages:
            target_page = pages[0]
            print(
                f"Warning: Could not match node-id to a page. Using first page: '{target_page['name']}'",
                file=sys.stderr,
            )
        else:
            print("Error: No pages found in this Figma file.", file=sys.stderr)
            sys.exit(1)

    print(f"Page: {target_page['name']}", file=sys.stderr)

    # Get top-level frames on this page
    frames = []
    for child in target_page.get("children", []):
        if child.get("type") == "FRAME":
            frames.append({
                "id": child["id"],
                "name": child.get("name", "Unnamed"),
                "x": child.get("absoluteBoundingBox", {}).get("x", 0),
                "y": child.get("absoluteBoundingBox", {}).get("y", 0),
            })

    # Sort by x-position (left to right), then y-position
    frames.sort(key=lambda f: (f["y"], f["x"]))

    return frames


# ---------------------------------------------------------------------------
# Review Engine
# ---------------------------------------------------------------------------

def load_skill() -> str:
    """Load the design review skill."""
    if not SKILL_PATH.exists():
        print(f"Error: Skill file not found at {SKILL_PATH}", file=sys.stderr)
        sys.exit(1)
    return SKILL_PATH.read_text()


def build_system_prompt(skill_text: str) -> str:
    """Build the system prompt for individual frame reviews."""
    return (
        "You are the Binocs Design Review Agent. You review Figma designs for Binocs — "
        "an industry analysis and investment memo platform for PE analysts, credit analysts, "
        "partners, and consultants in the United States.\n\n"
        "You are direct and blunt. Every issue gets a specific fix. No hedging.\n\n"
        f"## Design Review Skill\n\n{skill_text}\n\n"
        "## Instructions\n\n"
        "Review the provided frame against EVERY category (Sections 1–15) in the skill above. "
        "For this individual frame review, output a JSON array of issues. Each issue:\n"
        "```json\n"
        "{\n"
        '  "priority": "P0|P1|P2|P3",\n'
        '  "category": "Category name from skill",\n'
        '  "element": "Specific element name or layer path",\n'
        '  "problem": "What is wrong — specific and measurable",\n'
        '  "fix": "Exactly what to change",\n'
        '  "node_hint": "Best guess at which Figma node this applies to (for comment pinning)"\n'
        "}\n"
        "```\n"
        "Also include a `_positives` array with at least 2 things the frame does well.\n\n"
        "Output ONLY valid JSON. No markdown fences, no preamble.\n"
        f"Today: {datetime.now().strftime('%B %d, %Y')}"
    )


def build_flow_analysis_prompt(skill_text: str) -> str:
    """Build the system prompt for cross-frame flow analysis."""
    return (
        "You are the Binocs Design Review Agent performing a cross-frame flow analysis.\n\n"
        "You have already reviewed each frame individually. Now you are checking:\n"
        "1. FLOW CONTINUITY (Section 14): Every action on Frame N has a corresponding result state. "
        "Missing states are flagged.\n"
        "2. CROSS-FRAME CONSISTENCY: Same components must look identical across frames. "
        "Typography, colors, spacing, button styles — all must match.\n"
        "3. MISSING FRAMES: Common frames that should exist but are absent "
        "(empty states, error states, loading states, confirmation dialogs, etc.)\n\n"
        "Output JSON with three arrays:\n"
        "```json\n"
        "{\n"
        '  "continuity_issues": [{"priority": "...", "description": "...", "fix": "...", "between_frames": "Frame A → Frame B"}],\n'
        '  "consistency_issues": [{"priority": "...", "description": "...", "fix": "...", "frames_affected": ["Frame A", "Frame B"]}],\n'
        '  "missing_frames": [{"description": "...", "why_needed": "...", "priority": "..."}]\n'
        "}\n"
        "```\n"
        "Be thorough. Missing frames and broken continuity are among the most costly issues "
        "to fix after dev handoff.\n\n"
        "Output ONLY valid JSON. No markdown fences, no preamble."
    )


def _call_anthropic_with_retry(
    client: anthropic.Anthropic,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> anthropic.types.Message:
    """Call the Anthropic API with exponential backoff on transient errors."""
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)
                print(f"    Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
        except anthropic.InternalServerError:
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)
                print(f"    Server error. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    # Should not reach here, but satisfy type checker
    raise anthropic.APIError("Max retries exceeded")


def review_frame(
    client: anthropic.Anthropic,
    system_prompt: str,
    frame_name: str,
    design_context: dict,
    screenshot_b64: str | None = None,
) -> dict:
    """Review a single frame and return parsed issues."""
    user_content = []

    # Add screenshot if available
    if screenshot_b64:
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": screenshot_b64,
            },
        })

    # Add design context as text
    context_str = json.dumps(design_context, indent=2, default=str)
    # Truncate if extremely large (preserve start and end)
    if len(context_str) > 50000:
        context_str = context_str[:25000] + "\n\n... [truncated for size] ...\n\n" + context_str[-25000:]

    user_content.append({
        "type": "text",
        "text": (
            f"## Frame: {frame_name}\n\n"
            f"### Design Context (from Figma)\n```json\n{context_str}\n```\n\n"
            "Review this frame against all 15 categories. Return the JSON issues array."
        ),
    })

    try:
        message = _call_anthropic_with_retry(
            client,
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  Warning: Could not parse JSON for frame '{frame_name}'. Raw output saved.", file=sys.stderr)
        return {"_raw": message.content[0].text, "_parse_error": True}
    except anthropic.APIError as e:
        print(f"  Error reviewing frame '{frame_name}' after retries: {e}", file=sys.stderr)
        return {"_error": str(e)}


def analyze_flow(
    client: anthropic.Anthropic,
    skill_text: str,
    frame_names: list[str],
    all_frame_issues: dict[str, list],
    frame_screenshots: dict[str, str] | None = None,
) -> dict:
    """
    Run cross-frame flow analysis.

    Includes up to 8 evenly-spaced frame screenshots so the model can catch
    visual inconsistencies (button color mismatch, header height drift, etc.)
    that text summaries alone would miss.
    """
    system_prompt = build_flow_analysis_prompt(skill_text)

    # Build a summary of each frame's content and issues for the flow analysis
    frame_summaries = []
    for name in frame_names:
        issues = all_frame_issues.get(name, [])
        issue_summary = []
        for issue in issues:
            if isinstance(issue, dict) and "problem" not in issue:
                continue
            issue_summary.append(f"  - [{issue.get('priority', '?')}] {issue.get('category', '?')}: {issue.get('problem', '?')}")

        frame_summaries.append(
            f"### {name}\n"
            f"Issues found: {len(issue_summary)}\n"
            + ("\n".join(issue_summary) if issue_summary else "  No issues found")
        )

    # Build user content with both text and screenshots
    user_content: list[dict] = []

    # Include evenly-spaced screenshots for visual consistency checking
    if frame_screenshots:
        available = [(name, frame_screenshots[name]) for name in frame_names if name in frame_screenshots]
        # Pick up to 8 evenly spaced frames for visual reference
        max_screenshots = min(8, len(available))
        if max_screenshots > 0 and len(available) > 0:
            step = max(1, len(available) // max_screenshots)
            sampled = available[::step][:max_screenshots]
            for name, b64 in sampled:
                user_content.append({
                    "type": "text",
                    "text": f"[Screenshot: {name}]",
                })
                user_content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": b64},
                })

    user_content.append({
        "type": "text",
        "text": (
            f"## Flow: {len(frame_names)} frames\n\n"
            f"Frame sequence (in order): {', '.join(frame_names)}\n\n"
            "### Per-frame review summaries:\n\n"
            + "\n\n".join(frame_summaries)
            + "\n\nPerform the cross-frame analysis. Check flow continuity, visual consistency "
            "across the screenshots above, and missing frames."
        ),
    })

    try:
        message = _call_anthropic_with_retry(
            client,
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except (json.JSONDecodeError, anthropic.APIError) as e:
        print(f"  Warning: Flow analysis parse/API error: {e}", file=sys.stderr)
        return {"continuity_issues": [], "consistency_issues": [], "missing_frames": []}


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_report(
    flow_name: str,
    frame_names: list[str],
    all_issues: dict[str, list],
    flow_analysis: dict,
    positives: list[str],
) -> str:
    """Generate the final prioritized report."""
    today = datetime.now().strftime("%B %d, %Y")

    # Flatten all issues and sort by priority
    flat_issues = []
    for frame_name, issues in all_issues.items():
        for issue in issues:
            if isinstance(issue, dict) and "problem" in issue:
                issue["frame"] = frame_name
                flat_issues.append(issue)

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    flat_issues.sort(key=lambda x: priority_order.get(x.get("priority", "P3"), 4))

    # Group by priority
    grouped = {"P0": [], "P1": [], "P2": [], "P3": []}
    for issue in flat_issues:
        p = issue.get("priority", "P3")
        if p in grouped:
            grouped[p].append(issue)

    # Count totals
    total = len(flat_issues)
    p0_count = len(grouped["P0"])

    # Summary
    if p0_count > 0:
        verdict = f"NOT ready for dev handoff. {p0_count} blocking issue{'s' if p0_count != 1 else ''} found."
    elif len(grouped["P1"]) > 5:
        verdict = f"Needs work before dev handoff. {len(grouped['P1'])} must-fix issues found."
    else:
        verdict = "Close to ready for dev handoff with minor fixes."

    lines = [
        f"DESIGN REVIEW: {flow_name}",
        f"Reviewed: {today}",
        f"Frames reviewed: {len(frame_names)} — {', '.join(frame_names)}",
        f"Agent: Binocs Design Review Agent",
        f"Total issues: {total}",
        "",
        "━" * 60,
        "",
        "SUMMARY",
        verdict,
        "",
    ]

    # Issues by priority
    priority_labels = {
        "P0": "P0 — BLOCKERS (Do not hand off to dev until fixed)",
        "P1": "P1 — MUST FIX (Fix before dev handoff)",
        "P2": "P2 — SHOULD FIX (Fix during dev or next iteration)",
        "P3": "P3 — POLISH (Nice to have)",
    }

    for p_level in ["P0", "P1", "P2", "P3"]:
        issues = grouped[p_level]
        if not issues:
            continue
        lines.append("━" * 60)
        lines.append("")
        lines.append(priority_labels[p_level])
        lines.append("")
        for i, issue in enumerate(issues, 1):
            lines.append(f"  {i}. {issue.get('category', 'General')}: {issue.get('problem', '?')}")
            lines.append(f"     Frame: {issue.get('frame', '?')}")
            lines.append(f"     Element: {issue.get('element', '?')}")
            lines.append(f"     Fix: {issue.get('fix', '?')}")
            lines.append("")

    # Missing frames
    missing = flow_analysis.get("missing_frames", [])
    if missing:
        lines.append("━" * 60)
        lines.append("")
        lines.append("MISSING FRAMES")
        lines.append("")
        for m in missing:
            lines.append(f"  - [{m.get('priority', 'P1')}] {m.get('description', '?')}")
            lines.append(f"    Why needed: {m.get('why_needed', '?')}")
            lines.append("")

    # Flow continuity issues
    continuity = flow_analysis.get("continuity_issues", [])
    consistency = flow_analysis.get("consistency_issues", [])
    if continuity or consistency:
        lines.append("━" * 60)
        lines.append("")
        lines.append("FLOW CONTINUITY & CONSISTENCY ISSUES")
        lines.append("")
        for c in continuity:
            lines.append(f"  - [{c.get('priority', 'P1')}] {c.get('description', '?')}")
            lines.append(f"    Between: {c.get('between_frames', '?')}")
            lines.append(f"    Fix: {c.get('fix', '?')}")
            lines.append("")
        for c in consistency:
            lines.append(f"  - [{c.get('priority', 'P1')}] {c.get('description', '?')}")
            lines.append(f"    Frames affected: {', '.join(c.get('frames_affected', []))}")
            lines.append(f"    Fix: {c.get('fix', '?')}")
            lines.append("")

    # Positives
    lines.append("━" * 60)
    lines.append("")
    lines.append("WHAT'S WORKING WELL")
    lines.append("")
    for p in positives:
        lines.append(f"  - {p}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Comment Posting
# ---------------------------------------------------------------------------

def _post_comment_with_backoff(
    figma: FigmaClient, file_key: str, message: str, node_id: str,
    delay: float = 0.5,
) -> float:
    """Post a single Figma comment with adaptive rate limiting. Returns next delay."""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            figma.post_comment(file_key, message, node_id=node_id)
            time.sleep(delay)
            return max(0.5, delay * 0.9)  # Slowly reduce delay on success
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                delay = min(delay * 2, 10.0)  # Double delay, cap at 10s
                print(f"    Rate limited by Figma. Waiting {delay:.1f}s...", file=sys.stderr)
                time.sleep(delay)
            elif attempt < max_attempts - 1:
                time.sleep(1)
            else:
                raise
    return delay


def post_figma_comments(
    figma: FigmaClient,
    file_key: str,
    all_issues: dict[str, list],
    frame_id_map: dict[str, str],
    flow_analysis: dict,
) -> int:
    """Post issues as pinned Figma comments. Returns count of comments posted."""
    count = 0
    delay = 0.5  # Adaptive delay between comments

    for frame_name, issues in all_issues.items():
        frame_id = frame_id_map.get(frame_name)
        if not frame_id:
            continue

        for issue in issues:
            if not isinstance(issue, dict) or "problem" not in issue:
                continue

            priority = issue.get("priority", "P3")
            category = issue.get("category", "General")
            problem = issue.get("problem", "")
            fix = issue.get("fix", "")

            comment_text = f"[{priority}] {category}: {problem}. Fix: {fix}"

            try:
                delay = _post_comment_with_backoff(figma, file_key, comment_text, frame_id, delay)
                count += 1
            except requests.HTTPError as e:
                print(f"  Warning: Could not post comment on {frame_name}: {e}", file=sys.stderr)

    # Post flow-level comments on the last frame
    if frame_id_map:
        last_frame_id = list(frame_id_map.values())[-1]

        for issue in flow_analysis.get("continuity_issues", []):
            text = f"[{issue.get('priority', 'P1')}] Flow Continuity: {issue.get('description', '')}. Fix: {issue.get('fix', '')}"
            try:
                delay = _post_comment_with_backoff(figma, file_key, text, last_frame_id, delay)
                count += 1
            except requests.HTTPError:
                pass

        for mf in flow_analysis.get("missing_frames", []):
            text = f"[{mf.get('priority', 'P1')}] Missing Frame: {mf.get('description', '')}. {mf.get('why_needed', '')}"
            try:
                delay = _post_comment_with_backoff(figma, file_key, text, last_frame_id, delay)
                count += 1
            except requests.HTTPError:
                pass

    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Binocs Design Review Agent — review Figma designs against Binocs standards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="Figma file or page URL to review")
    parser.add_argument("--output", "-o", help="Save report to this file path")
    parser.add_argument("--frames", help="Comma-separated frame names to review (default: all on page)")
    parser.add_argument("--comment", action="store_true", help="Post issues as pinned Figma comments")

    args = parser.parse_args()

    # Validate environment
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: Set ANTHROPIC_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    figma_token = os.environ.get("FIGMA_ACCESS_TOKEN")
    if not figma_token:
        print("Error: Set FIGMA_ACCESS_TOKEN environment variable.", file=sys.stderr)
        sys.exit(1)

    # Parse URL
    file_key, page_node_id = parse_figma_url(args.url)
    print(f"File key: {file_key}", file=sys.stderr)

    # Initialize clients
    figma = FigmaClient(figma_token)
    anthropic_client = anthropic.Anthropic()

    # Discover frames
    print("Discovering frames...", file=sys.stderr)
    frames = discover_frames(figma, file_key, page_node_id)

    if not frames:
        print("Error: No frames found on this page.", file=sys.stderr)
        sys.exit(1)

    # Filter frames if specified
    if args.frames:
        filter_names = {n.strip() for n in args.frames.split(",")}
        all_frame_names = [f["name"] for f in frames]
        frames = [f for f in frames if f["name"] in filter_names]
        if not frames:
            print(f"Error: None of the specified frames found. Available: {all_frame_names}", file=sys.stderr)
            sys.exit(1)

    frame_names = [f["name"] for f in frames]
    frame_id_map = {f["name"]: f["id"] for f in frames}
    print(f"Found {len(frames)} frames: {', '.join(frame_names)}", file=sys.stderr)

    # Load skill and build prompts
    skill_text = load_skill()
    system_prompt = build_system_prompt(skill_text)

    # Review frames in batches
    all_issues: dict[str, list] = {}
    all_positives: list[str] = []
    all_screenshots: dict[str, str] = {}  # frame_name → base64 screenshot for flow analysis

    for batch_start in range(0, len(frames), BATCH_SIZE):
        batch = frames[batch_start : batch_start + BATCH_SIZE]
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (len(frames) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\nBatch {batch_num}/{total_batches}: {[f['name'] for f in batch]}", file=sys.stderr)

        # Get design context for this batch
        batch_ids = [f["id"] for f in batch]

        try:
            nodes_data = figma.get_file_nodes(file_key, batch_ids)
        except requests.HTTPError as e:
            print(f"  Error fetching node data: {e}", file=sys.stderr)
            nodes_data = {"nodes": {}}

        # Get screenshots for this batch
        try:
            image_urls = figma.get_images(file_key, batch_ids)
        except requests.HTTPError as e:
            print(f"  Warning: Could not get screenshots: {e}", file=sys.stderr)
            image_urls = {}

        # Review each frame in the batch
        for frame in batch:
            print(f"  Reviewing: {frame['name']}...", file=sys.stderr)

            # Get design context
            node_data = nodes_data.get("nodes", {}).get(frame["id"], {})
            design_context = node_data.get("document", {})

            # Get screenshot
            screenshot_b64 = None
            img_url = image_urls.get(frame["id"])
            if img_url:
                try:
                    img_bytes = figma.download_image(img_url)
                    screenshot_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
                    all_screenshots[frame["name"]] = screenshot_b64
                except Exception as e:
                    print(f"    Warning: Could not download screenshot: {e}", file=sys.stderr)

            # Review
            result = review_frame(
                anthropic_client, system_prompt, frame["name"], design_context, screenshot_b64
            )

            if isinstance(result, dict) and ("_parse_error" in result or "_error" in result):
                print(f"    Warning: Review had issues. See raw output.", file=sys.stderr)
                all_issues[frame["name"]] = []
            else:
                # Parse issues and positives from the API response.
                # The prompt asks for a JSON array of issues with a _positives key,
                # but the model may return either a list or a dict wrapper.
                issues: list[dict] = []
                positives: list[str] = []

                if isinstance(result, list):
                    # Model returned a flat array — items with "problem" are issues
                    issues = [item for item in result if isinstance(item, dict) and "problem" in item]
                elif isinstance(result, dict):
                    # Model returned a dict — extract issues from known keys
                    positives = result.get("_positives", [])
                    if "issues" in result:
                        issues = result["issues"]
                    elif "_issues" in result:
                        issues = result["_issues"]
                    else:
                        # Issues may be in non-underscore keys
                        for key, val in result.items():
                            if key.startswith("_"):
                                continue
                            if isinstance(val, list):
                                issues.extend(
                                    item for item in val
                                    if isinstance(item, dict) and "problem" in item
                                )

                all_issues[frame["name"]] = issues
                if isinstance(positives, list):
                    all_positives.extend(positives)

                print(f"    Found {len(issues)} issues.", file=sys.stderr)

    # Cross-frame flow analysis
    print("\nRunning cross-frame analysis...", file=sys.stderr)
    flow_analysis = analyze_flow(
        anthropic_client, skill_text, frame_names, all_issues,
        frame_screenshots=all_screenshots,
    )

    cont_count = len(flow_analysis.get("continuity_issues", []))
    cons_count = len(flow_analysis.get("consistency_issues", []))
    miss_count = len(flow_analysis.get("missing_frames", []))
    print(
        f"  Flow issues: {cont_count} continuity, {cons_count} consistency, {miss_count} missing frames",
        file=sys.stderr,
    )

    # Determine flow name from first frame or page
    flow_name = frame_names[0].split(" - ")[0] if frame_names else "Unknown Flow"

    # Generate report
    print("\nGenerating report...", file=sys.stderr)
    report = generate_report(flow_name, frame_names, all_issues, flow_analysis, all_positives[:6])

    # Post Figma comments if requested
    if args.comment:
        print("\nPosting Figma comments...", file=sys.stderr)
        comment_count = post_figma_comments(figma, file_key, all_issues, frame_id_map, flow_analysis)
        print(f"  Posted {comment_count} comments.", file=sys.stderr)

    # Output
    if args.output:
        Path(args.output).write_text(report)
        print(f"\nReport saved to: {args.output}", file=sys.stderr)
    else:
        print("\n" + report)

    # Summary
    total_issues = sum(len(v) for v in all_issues.values())
    print(f"\nDone. {total_issues} issues across {len(frame_names)} frames.", file=sys.stderr)


if __name__ == "__main__":
    main()
