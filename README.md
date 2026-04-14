# Binocs Design Review Agent

An automated UI/UX review agent that reviews Figma designs for **Binocs** against Tier 1 B2B design standards, tailored for PE/credit analyst users.

Built for Product Managers to review designer output before developer handoff.

## What It Reviews

The agent evaluates every frame in a Figma flow against **15 categories**:

| # | Category | What It Checks |
|---|----------|---------------|
| 1 | Visual Design & Modernity | Spacing grid (4px), elevation, icons, status indicators, tables |
| 2 | Typography System | Font hierarchy, sizes, weights, line-height, number formatting |
| 3 | Color System | 60-30-10 rule, semantic colors, contrast ratios, data-viz colors |
| 4 | Copy, Microcopy & Grammar | Finance-native tone, spelling, punctuation, CTA copy, date/number formats |
| 5 | UX Clarity & IA | Primary task clarity, information hierarchy, navigation, filters |
| 6 | Action Design & CTAs | Deduplication, visual hierarchy of actions, microcopy near CTAs |
| 7 | Form UX | Labels, validation, progressive profiling, dropdowns |
| 8 | Component State Coverage | Hover, active, disabled, loading, error, success, empty — for every interactive element |
| 9 | Minimalism | Element economy, redundancy, decorative clutter |
| 10 | Accessibility (WCAG 2.1 AA) | Contrast, keyboard nav, screen reader labels, touch targets |
| 11 | Data Visualization | Charts, tables, financial data formatting, colorblind safety |
| 12 | Micro-interactions & Motion | Hover states, transitions, loading states, feedback |
| 13 | Edge Cases & Responsive | Text overflow, 0/1/1000 items, empty states, error states |
| 14 | Flow Continuity | Missing states, broken transitions, dead ends, cross-frame consistency |
| 15 | Trust & Confidence Signals | Data freshness, source attribution, destructive action safety |

## How to Use

### Option A — Claude Code (Recommended)

This is the primary way to use the agent. Open the project in Claude Code and talk to it.

**Setup:**
1. Clone this repo
2. Open it in Claude Code: `claude` (from the project root)
3. Ensure the Figma MCP is connected (the `.mcp.json` handles this)
4. Authenticate with Figma when prompted

**Usage:**
```
> Review this flow: https://www.figma.com/design/abc123/Binocs?node-id=456:789
```

Claude Code will:
1. Discover all frames on the page
2. Review each frame against all 15 categories
3. Run cross-frame flow analysis
4. Post pinned comments to specific Figma elements
5. Generate a prioritized report

### Option B — Standalone Script

For automated/CI usage without Claude Code.

**Setup:**
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
export FIGMA_ACCESS_TOKEN="your-figma-personal-access-token"
```

**Usage:**
```bash
# Review all frames on a page
python design_review_agent.py "https://www.figma.com/design/FILE_KEY/Binocs?node-id=PAGE_ID"

# Save report to file
python design_review_agent.py "https://..." --output review.txt

# Post comments to Figma
python design_review_agent.py "https://..." --comment

# Review specific frames only
python design_review_agent.py "https://..." --frames "Frame 1,Frame 2,Frame 3"
```

## Output Format

### Figma Comments (pinned to specific elements)
```
[P0] Typography: Body text is 11px — below 14px minimum. Fix: Increase to 14px.
[P1] States: This button has no hover or disabled state. Add all interactive states.
[P2] Copy: "Genearted" is misspelled. Fix: Change to "Generated."
```

### Report (prioritized by severity)
```
DESIGN REVIEW: CDD Industry Report
Reviewed: April 14, 2026
Frames reviewed: 12

P0 — BLOCKERS (Do not hand off to dev until fixed)
  1. Typography: Body text 11px on report detail view...

P1 — MUST FIX (Fix before dev handoff)
  1. States: Export button missing hover/disabled states...

P2 — SHOULD FIX
  ...

MISSING FRAMES
  - No error state for data fetch on Industry Overview...

FLOW CONTINUITY ISSUES
  - Save button on Frame 3 has no success confirmation in Frame 4...
```

## Priority Levels

| Level | Meaning | Examples |
|-------|---------|---------|
| **P0** | Blocker — do not hand off to dev | Accessibility failure, misleading data, broken flow, missing critical frame |
| **P1** | Must fix before dev handoff | Spelling errors, missing component states, spacing violations, inconsistent styling |
| **P2** | Fix during dev or next iteration | Minor copy improvements, subtle visual polish, non-critical edge cases |
| **P3** | Nice to have | Refinements, suggestions, future improvements |

## Project Structure

```
.
├── CLAUDE.md                              # Claude Code orchestration instructions
├── .claude/skills/design-review/SKILL.md  # The review knowledge base (15 categories)
├── .mcp.json                              # Figma MCP server config
├── design_review_agent.py                 # Standalone Python agent
├── requirements.txt                       # Python dependencies
└── README.md
```

## Audience Context

This agent is calibrated for **Binocs** — an industry analysis and investment memo platform. All review decisions account for the target users:

- PE associates, VPs, principals, and managing partners
- Credit analysts at lending institutions
- Investment committee members
- US-based, 28–55 years old, extremely time-constrained
- UX baseline: Bloomberg, PitchBook, Carta, Capital IQ

The agent enforces **institutional-grade polish** — not consumer SaaS aesthetics.
