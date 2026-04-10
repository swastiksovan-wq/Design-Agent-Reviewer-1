---
name: design-review
description: Review Figma designs, screenshots, or UI implementations against Binocs design standards for PE/credit analyst users. Covers action deduplication, copy clarity, visual modernity, UX clarity, minimalism, accessibility, and edge case handling.
user_invocable: true
---

# Binocs Design Review Skill

## Purpose

This skill provides design review guidelines for **Binocs** — an industry analysis and investment memo platform built for **Private Equity analysts, credit analysts, and partners in the United States**. Use this skill to review any Figma design, screenshot, or UI implementation for compliance with Binocs design standards.

When reviewing a design, evaluate it against every section below and produce a structured report with severity levels: `🔴 Critical`, `🟡 Warning`, `🟢 Pass`.

---

## How to Use This Skill

### With Figma MCP

When the user provides a Figma URL:
1. Use the Figma MCP `get_design_context` tool to retrieve structured design data (layout, typography, colors, components)
2. Analyze the returned data against every section in this skill
3. Produce a structured review report in the output format defined in Section 9

### With a Screenshot

When the user provides a screenshot:
1. Read the screenshot image to understand the UI
2. Analyze every visible element against the rules below
3. Produce a structured review report

### For PR/CI Review

When reviewing UI changes in a PR:
1. Compare before/after screenshots or Figma frames
2. Flag any regressions against the standards below
3. Focus on changes — don't re-review unchanged areas unless they interact with changes

---

## 1. Audience Context

Binocs users are senior finance professionals. Every design decision must respect this context.

### Who They Are
- Private Equity associates, VPs, principals, and partners
- Credit analysts at lending institutions and direct lenders
- Investment committee members reviewing deal flow
- Users are typically 28–55 years old, US-based, and time-constrained

### What They Expect
- **Institutional-grade polish**: The UI must feel as trustworthy as a Bloomberg terminal or PitchBook, not like a consumer SaaS tool
- **Zero learning curve**: Every interaction should be self-evident; these users will not read help docs
- **Density without clutter**: They want to see a lot of data at once, but it must be scannable — not overwhelming
- **Speed and efficiency**: They frequently compare multiple reports side-by-side and switch between industries rapidly

### Review Checklist — Audience Fit
- [ ] Does the design feel appropriate for a $500M+ AUM fund environment?
- [ ] Would a managing director be comfortable showing this on-screen during an investment committee meeting?
- [ ] Is financial data presented with appropriate precision and formatting (e.g., $356.11M not $356.11 M)?
- [ ] Are industry-standard terms used correctly (CAGR, TAM, not "growth rate," "total market")?

---

## 2. Action Deduplication & Redundancy

**Principle**: Every interactive element must have a single, clear purpose. No two elements on the same view should perform the same or overlapping action.

### Rules

1. **No duplicate CTAs**: If a row has a share icon, it must not also have a "Share" option in a kebab (⋮) menu for the same scope. Choose one surface.
2. **No redundant navigation paths**: If a sidebar link navigates to a page, the page title must not also be a clickable link to the same page.
3. **Consolidate contextual actions**: Row-level actions (edit, delete, share, archive) should live in a single interaction point — preferably a kebab menu (⋮) — not scattered across the row as individual icons.
4. **Primary vs. secondary action separation**: Each view should have at most **one** primary action button (e.g., "+ Industry Analysis"). All other actions are secondary and should be visually subordinate.
5. **Filter deduplication**: If "Status" is a dropdown filter, there should not also be separate toggle buttons for individual statuses (e.g., "Unread" toggle + Status dropdown that includes "Unread").

### Review Checklist — Redundancy
- [ ] Count all interactive elements per row/card. Are any two doing the same thing?
- [ ] Is there more than one primary-styled button on screen?
- [ ] Do filters overlap in scope?
- [ ] Are there actions that exist both inline AND in a menu?
- [ ] Can any two buttons/links lead to the exact same outcome?

### Known Issues
- Share icon (↗) alongside kebab menu (⋮): Consolidate into one surface
- Duplicate data entries should surface a warning or merge indicator

---

## 3. Copy & Microcopy Standards

**Principle**: Every word must earn its place. Copy should be precise, professional, and free of ambiguity — written for people who read term sheets, not marketing pages.

### Rules

1. **Use finance-native language**: "Market Size & CAGR" is correct. Avoid consumer terms like "How big is the market?"
2. **Status labels must be actionable**: "Form Incomplete" is vague. Prefer: "Missing: [Geography, Market Size]" or "Draft — Incomplete."
3. **Empty states must guide**: "Not available" is unhelpful. Instead: "Complete the analysis form to generate market data."
4. **Tooltips over jargon**: Abbreviations (CAGR, TAM, MOIC) need a tooltip on first occurrence per session.
5. **Dates concise**: "Generated Apr 9, 2026" not "Report Generated on Apr 9, 2026 at 1:01 AM."
6. **Number formatting**: Always `$356.11M` (no space before M/B), `8.20% CAGR`, `$528.11M by 2031`. Never mix formats.
7. **Button labels verb-first**: "+ Industry Analysis" is good. Avoid noun-only labels.

### Review Checklist — Copy
- [ ] Is every label unambiguous?
- [ ] Are empty/null states descriptive and actionable?
- [ ] Is date formatting consistent and concise?
- [ ] Are numbers formatted correctly ($, M, B, %, commas)?
- [ ] Do all CTAs start with a verb or action symbol (+, →)?
- [ ] Is copy appropriately concise for the space?
- [ ] Is tone consistently professional?

---

## 4. Visual Design & Modernity

**Principle**: The design must feel current (2025–2026 standards), trustworthy, and quietly sophisticated. Not trendy — timeless.

### Aesthetic Direction
- **Refined institutional**: Think Linear, Carta, or Ramp — not Notion or Figma
- **Color palette**: Neutral base (white/near-white backgrounds, slate/charcoal text). Single brand accent for primary actions. Data-viz colors distinct but muted — no neon.
- **Typography**: Professional sans-serif (Inter, SF Pro, or comparable). Max 2 font weights per view (regular + semibold). Body: 14px min. Captions: 12px min.

### Rules

1. **Card/row elevation**: Subtle borders (`1px solid #E5E7EB`) over drop shadows. Shadows must be barely perceptible (`0 1px 2px rgba(0,0,0,0.05)`).
2. **Spacing system**: Strict 4px/8px grid. All padding, margins, gaps must be multiples of 4.
3. **Icon style**: Single icon family (Lucide, Phosphor, or similar). Never mix filled/outlined. Icons: 16px or 20px.
4. **Status indicators**: Small filled circles (8px) with semantic colors: green (complete), amber (in-progress), red (error). Avoid large badges/pills.
5. **Image thumbnails**: Consistent aspect ratio (16:9 or 1:1), `object-fit: cover`, border-radius 4–6px. Placeholders use branded initial or icon.
6. **Table density**: Target 40–48px row height for analyst data tables.
7. **Hover and focus states**: Every interactive element needs visible hover state. Focus rings required for keyboard navigation.

### Review Checklist — Visual Design
- [ ] Consistent spacing scale (multiples of 4 or 8)?
- [ ] Shadows, borders, elevation consistent?
- [ ] Clear visual hierarchy (Title → metadata → data → actions)?
- [ ] Status indicators small, semantic, consistent?
- [ ] Placeholder/empty states visually designed?
- [ ] Color palette restrained (≤1 accent + neutrals + semantic)?
- [ ] Would this fit alongside Carta, PitchBook, or Ramp?

### Known Issues
- Thumbnail inconsistency: initial-style placeholders need deterministic background colors (name-hash based)
- "V1" badge treatment: visually noisy — move version info to detail view or tooltip

---

## 5. UX Clarity & Information Architecture

**Principle**: A first-time user with PE experience should understand every element on screen within 5 seconds.

### Rules

1. **One primary task per view**: The list page's primary task is "find and open a report." Everything else is secondary.
2. **Progressive disclosure**: Show minimum for scanning in list view. Details in expanded row or detail page.
3. **Filter bar clarity**: Show current state. Use chip-style active filters or count ("2 filters active").
4. **Sort affordance**: Every sortable column must show a sort icon.
5. **Empty vs. incomplete distinction**: Muted style for "no data yet," soft warning for "action required."
6. **Consistent row structure**: Every row must have same columns and visual weight.
7. **Sidebar navigation**: Active nav must be clearly highlighted — background highlight or left-border accent.

### Review Checklist — UX Clarity
- [ ] Can a new user identify the primary action within 3 seconds?
- [ ] Clear information hierarchy?
- [ ] Filters communicate current state?
- [ ] Sortable columns clearly indicated?
- [ ] "Empty" vs. "incomplete" vs. "error" visually distinct?
- [ ] Sidebar clearly indicates current location?
- [ ] Clear path from list → detail → action?

### Known Issues
- "Not available" overload: collapse incomplete rows into compact "draft" treatment
- Credits indicator: if credits gate actions, surface cost at point of action

---

## 6. Minimalism & Element Economy

**Principle**: If removing an element does not reduce understanding or functionality, remove it.

### Rules

1. **No decorative-only elements**: No ornamental dividers, icons, or flair without function.
2. **Reduce label repetition**: Same label on max 2 surfaces (e.g., sidebar + page title, not also breadcrumb).
3. **Consolidate metadata**: Group related metadata into a single styled line with clear separators.
4. **Minimize chrome**: Use borders/dividers only when spacing alone doesn't create clear grouping.
5. **Limit filter controls**: Move rarely-used filters to "Advanced filters" expansion.
6. **Badge economy**: One status indicator per item in list view. Additional context in detail view.

### Review Checklist — Minimalism
- [ ] Remove one element — does anything break? If not, remove it.
- [ ] Any purely decorative elements?
- [ ] Same information shown in more than 2 places?
- [ ] Could adjacent elements be combined?
- [ ] Every filter/control earning its screen real estate?
- [ ] More than 2 visual indicators on any single row?

### Known Issues
- Zero-count toggles ("Unread (0)", "Archived Reports (0)") add weight with no value — hide or collapse
- Excessive columns: consider moving "Key Players" to detail view only

---

## 7. Accessibility & Compliance

**Principle**: Institutional US clients expect ADA-compliant, WCAG 2.1 AA-level interfaces.

### Rules

1. **Color contrast**: WCAG AA — 4.5:1 normal text, 3:1 large text (≥18px or ≥14px bold). Check green-on-white and light-grey-on-white specifically.
2. **Keyboard navigation**: Every mouse action must work via keyboard. Tab order follows visual order.
3. **Screen reader labels**: Icon buttons need `aria-label` (e.g., "Share Mochi Ice cream report", "More actions for Mochi Ice cream").
4. **Focus indicators**: Never remove `outline` without an alternative visible indicator.
5. **Touch targets**: ≥44×44px on touch/responsive layouts.
6. **Status communication**: Color must never be the sole indicator — pair with text labels or icons (✓/✗).

### Review Checklist — Accessibility
- [ ] All text/background meet WCAG AA contrast?
- [ ] Every action keyboard-accessible?
- [ ] Icon-only buttons have aria-labels?
- [ ] Status communicated beyond just color?
- [ ] Focus indicators visible?
- [ ] Touch targets ≥44px on responsive?

---

## 8. Responsive & Edge Case Handling

### Rules

1. **Long text truncation**: Truncate with ellipsis + tooltip. Never break row height consistency.
2. **Data range formatting**: Use en-dash with spaces: "$463M – $528M" (simplify decimals where unnecessary).
3. **Empty list state**: Designed state with illustration/icon + headline + description + primary CTA. Never empty table with just headers.
4. **Bulk actions**: Selection UI appears contextually — top bar replaces filters when items selected.
5. **Loading states**: Skeleton/shimmer for every data area. "Loading your analyses..." not just a spinner.
6. **Error states**: Inline errors per section, not full-page. Show list with error badges on affected rows.

### Review Checklist — Edge Cases
- [ ] What does this look like with 0, 1, and 1,000 items?
- [ ] All text fields truncation-safe with tooltips?
- [ ] Loading state designed?
- [ ] Error state designed?
- [ ] Layout survives extreme data (long names, large numbers, many segments)?

---

## 9. Review Output Format

Always structure design review feedback as follows:

```
## Design Review: [Screen/Component Name]
### Date: [Date]
### Reviewer: Claude (Design Review Agent)

---

### Summary
[2–3 sentence overall assessment]

### 🔴 Critical Issues (Must fix before ship)
1. **[Issue title]**
   - Location: [Where in the UI]
   - Problem: [What's wrong]
   - Impact: [Why it matters for the user/business]
   - Recommendation: [Specific fix]

### 🟡 Warnings (Should fix, not blocking)
1. **[Issue title]**
   - Location: [Where in the UI]
   - Problem: [What's wrong]
   - Recommendation: [Specific fix]

### 🟢 What's Working Well
- [Positive observations — always include at least 2]

### 📊 Scores
| Category                | Score (1–5) | Notes                  |
|------------------------|-------------|------------------------|
| Audience Fit           | X           |                        |
| Action Deduplication   | X           |                        |
| Copy & Microcopy       | X           |                        |
| Visual Modernity       | X           |                        |
| UX Clarity             | X           |                        |
| Minimalism             | X           |                        |
| Accessibility          | X           |                        |
| Edge Case Handling     | X           |                        |
| **Overall**            | **X**       |                        |
```
