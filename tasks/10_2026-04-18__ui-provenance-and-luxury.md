# Task: UI/UX Terminal Luxury & Data Provenance

## Goal
Build a foundational analytical interface focusing on Data Provenance and a "Terminal Luxury" aesthetic. This structure must emphasize deterministic runs and absolute transparency.

## Done means
- [x] Implement dark mode theme (true black/slate) using `Inter` for UI and `JetBrains Mono` for numerical data.
- [x] Build the "Screener Table" (Dashboard Cockpit) configured to show vital deterministic columns.
- [x] Implement the **Workflow Control Center** for monitoring and managing Walter OS tasks.
- [x] Create a **WebSocket-based Terminal Console** for live log streaming in the UI.
- [x] Create **run_scanner.bat** for a one-click desktop launch experience.
- [x] `scripts/check.*` passes

## Constraints / must not change
- Keep the UI strictly functional (facts first, no persuasion).
- Lane A (Deterministic) must dominate within the Snapshot Page.

## Scope
IN:
- High-density Screener Table layout focusing only on vital deterministic columns.
- Dedicated Individual Company Snapshot Page ("Reason Card") routing/drawer component.
- Visual indicators for NCAV trend warnings on the Reason Card.
- CSS/Styling updates for dark mode and typography.
- Tooltip/popover components for data provenance.

OUT:
- Changing the underlying dataset computations or schema structure.

## Suggested files (optional)
- `ui_concept.md`
- Any frontend component files (e.g., `index.css`, `ReasonCard` component).
