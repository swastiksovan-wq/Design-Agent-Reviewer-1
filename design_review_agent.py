"""
Binocs Design Review Agent

Automated workflow that reviews Figma designs against Binocs design standards.
Uses Claude API with the Figma MCP server for structured design analysis.

Usage:
    # Review a Figma file
    python design_review_agent.py --figma-url "https://www.figma.com/design/FILE_KEY/..."

    # Review a screenshot
    python design_review_agent.py --screenshot path/to/screenshot.png

    # Review with focus areas
    python design_review_agent.py --figma-url "..." --focus "accessibility,copy"

    # Output to file
    python design_review_agent.py --figma-url "..." --output review.md
"""

from __future__ import annotations
import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

# ---------------------------------------------------------------------------
# Design review skill (loaded from SKILL.md at runtime)
# ---------------------------------------------------------------------------

SKILL_PATH = Path(__file__).parent / ".claude" / "skills" / "design-review" / "SKILL.md"

REVIEW_CATEGORIES = [
    "Audience Fit",
    "Action Deduplication",
    "Copy & Microcopy",
    "Visual Modernity",
    "UX Clarity",
    "Minimalism",
    "Accessibility",
    "Edge Case Handling",
]

FOCUS_AREA_MAP = {
    "audience": "Audience Fit",
    "deduplication": "Action Deduplication",
    "redundancy": "Action Deduplication",
    "copy": "Copy & Microcopy",
    "microcopy": "Copy & Microcopy",
    "visual": "Visual Modernity",
    "design": "Visual Modernity",
    "ux": "UX Clarity",
    "clarity": "UX Clarity",
    "ia": "UX Clarity",
    "minimalism": "Minimalism",
    "accessibility": "Accessibility",
    "a11y": "Accessibility",
    "edge": "Edge Case Handling",
    "responsive": "Edge Case Handling",
}


def load_skill() -> str:
    """Load the design review skill from SKILL.md."""
    if not SKILL_PATH.exists():
        print(f"Error: Skill file not found at {SKILL_PATH}", file=sys.stderr)
        print("Run the setup steps first to create the skill file.", file=sys.stderr)
        sys.exit(1)
    return SKILL_PATH.read_text()


def encode_image(image_path: str) -> tuple[str, str]:
    """Read and base64-encode an image file. Returns (base64_data, media_type)."""
    path = Path(image_path)
    if not path.exists():
        print(f"Error: Image not found at {image_path}", file=sys.stderr)
        sys.exit(1)

    suffix = path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/png")
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


def build_review_prompt(
    skill_text: str,
    focus_areas: Optional[list[str]] = None,
    figma_context: Optional[str] = None,
) -> str:
    """Build the system + user prompt for the design review."""
    focus_instruction = ""
    if focus_areas:
        resolved = []
        for area in focus_areas:
            key = area.strip().lower()
            if key in FOCUS_AREA_MAP:
                resolved.append(FOCUS_AREA_MAP[key])
            else:
                resolved.append(area.strip())
        focus_instruction = (
            f"\n\n**Focus Areas**: Pay extra attention to these categories "
            f"(still review all, but go deeper here): {', '.join(resolved)}"
        )

    figma_section = ""
    if figma_context:
        figma_section = (
            f"\n\n## Figma Design Context\n\n"
            f"The following structured design data was retrieved from Figma:\n\n"
            f"```json\n{figma_context}\n```"
        )

    return (
        f"You are the Binocs Design Review Agent. Your job is to review UI designs "
        f"against the Binocs design standards.\n\n"
        f"## Design Review Skill\n\n{skill_text}\n\n"
        f"## Instructions\n\n"
        f"Review the provided design against EVERY section of the skill above. "
        f"Produce a structured report using the exact output format from Section 9 "
        f"of the skill. Be specific — reference exact elements, locations, and values. "
        f"Score each category 1–5 where:\n"
        f"- 5 = Exemplary, no issues\n"
        f"- 4 = Good, minor polish needed\n"
        f"- 3 = Acceptable, several improvements needed\n"
        f"- 2 = Below standard, significant issues\n"
        f"- 1 = Failing, major redesign needed\n\n"
        f"Today's date: {datetime.now().strftime('%B %d, %Y')}"
        f"{focus_instruction}"
        f"{figma_section}"
    )


def review_screenshot(
    screenshot_path: str,
    focus_areas: Optional[list[str]] = None,
) -> str:
    """Review a screenshot against the design skill."""
    skill_text = load_skill()
    prompt = build_review_prompt(skill_text, focus_areas)
    image_data, media_type = encode_image(screenshot_path)

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Review this UI design against the Binocs design standards. "
                            "Analyze every visible element and produce the full structured report."
                        ),
                    },
                ],
            }
        ],
    )
    return message.content[0].text


def review_figma(
    figma_url: str,
    focus_areas: Optional[list[str]] = None,
) -> str:
    """
    Review a Figma design using Claude with Figma MCP tools.

    This uses Claude's tool_use capability to call Figma MCP endpoints,
    then analyzes the returned design data against the skill.
    """
    skill_text = load_skill()

    # Extract file key from Figma URL
    # URLs look like: https://www.figma.com/design/FILE_KEY/Name?node-id=...
    file_key = None
    node_id = None
    if "/design/" in figma_url or "/file/" in figma_url:
        parts = figma_url.split("/")
        for i, part in enumerate(parts):
            if part in ("design", "file") and i + 1 < len(parts):
                file_key = parts[i + 1]
                break
    if "node-id=" in figma_url:
        node_id = figma_url.split("node-id=")[1].split("&")[0]

    if not file_key:
        print("Error: Could not extract file key from Figma URL.", file=sys.stderr)
        print("Expected format: https://www.figma.com/design/FILE_KEY/...", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()

    # Step 1: Use Claude to call Figma MCP and retrieve design context
    figma_tools = [
        {
            "name": "get_design_context",
            "description": (
                "Retrieve structured design data from a Figma file including "
                "layout, typography, colors, components, and spacing."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_key": {
                        "type": "string",
                        "description": "The Figma file key extracted from the URL.",
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Optional specific node/frame ID to focus on.",
                    },
                },
                "required": ["file_key"],
            },
        }
    ]

    print("Fetching design context from Figma...", file=sys.stderr)

    # Initial request to get Claude to call the Figma tool
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=(
            "You are a design analysis assistant. Use the get_design_context tool "
            "to retrieve design data from the Figma file, then analyze it thoroughly."
        ),
        tools=figma_tools,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Retrieve the design context from this Figma file.\n"
                    f"File key: {file_key}"
                    + (f"\nNode ID: {node_id}" if node_id else "")
                ),
            }
        ],
    )

    # Check if Claude wants to use a tool
    figma_context = None
    if response.stop_reason == "tool_use":
        for block in response.content:
            if block.type == "tool_use":
                tool_input = block.input
                print(
                    f"Figma tool called with: {json.dumps(tool_input, indent=2)}",
                    file=sys.stderr,
                )
                # In a live MCP setup, this would be routed to the Figma MCP server.
                # For now, we note that the tool call was made correctly.
                print(
                    "\nNote: To complete this review with live Figma data, run this "
                    "command inside Claude Code where the Figma MCP server is connected.\n"
                    "The agent correctly identified the file and requested design context.\n",
                    file=sys.stderr,
                )
                figma_context = json.dumps(
                    {
                        "status": "mcp_tool_call_prepared",
                        "tool": "get_design_context",
                        "input": tool_input,
                        "note": (
                            "In a live MCP environment, this would return structured "
                            "design data. Use this agent inside Claude Code with the "
                            "Figma MCP server connected for full functionality."
                        ),
                    },
                    indent=2,
                )

    # Step 2: Generate the review
    print("Generating design review...", file=sys.stderr)
    review_prompt = build_review_prompt(skill_text, focus_areas, figma_context)

    review_message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=review_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Review the Figma design at: {figma_url}\n\n"
                    f"File key: {file_key}\n"
                    + (f"Node ID: {node_id}\n" if node_id else "")
                    + (
                        f"\nDesign context:\n```json\n{figma_context}\n```"
                        if figma_context
                        else "\nNote: No live Figma data available. Provide general "
                        "guidance based on the URL and known issues from the skill."
                    )
                ),
            }
        ],
    )
    return review_message.content[0].text


def main():
    parser = argparse.ArgumentParser(
        description="Binocs Design Review Agent — review designs against Binocs standards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python design_review_agent.py --screenshot mockup.png\n'
            '  python design_review_agent.py --figma-url "https://figma.com/design/abc123/..."\n'
            '  python design_review_agent.py --screenshot mockup.png --focus "accessibility,copy"\n'
            '  python design_review_agent.py --screenshot mockup.png --output review.md'
        ),
    )
    parser.add_argument(
        "--figma-url",
        help="Figma file URL to review",
    )
    parser.add_argument(
        "--screenshot",
        help="Path to a screenshot image to review",
    )
    parser.add_argument(
        "--focus",
        help="Comma-separated focus areas (e.g., 'accessibility,copy,ux')",
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: print to stdout)",
    )

    args = parser.parse_args()

    if not args.figma_url and not args.screenshot:
        parser.error("Provide either --figma-url or --screenshot")

    focus_areas = args.focus.split(",") if args.focus else None

    # Run the review
    if args.screenshot:
        print(f"Reviewing screenshot: {args.screenshot}", file=sys.stderr)
        result = review_screenshot(args.screenshot, focus_areas)
    else:
        print(f"Reviewing Figma design: {args.figma_url}", file=sys.stderr)
        result = review_figma(args.figma_url, focus_areas)

    # Output
    if args.output:
        Path(args.output).write_text(result)
        print(f"\nReview saved to: {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
