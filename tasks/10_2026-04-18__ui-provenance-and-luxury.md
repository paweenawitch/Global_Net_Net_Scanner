# Task: UI/UX Terminal Luxury & Data Provenance

## Goal
Build a foundational analytical interface focusing on Data Provenance and a "Terminal Luxury" aesthetic. This structure must emphasize deterministic runs and absolute transparency.

## Done means
- [ ] Implement dark mode theme (true black/slate) using `Inter` for UI and `JetBrains Mono`/`Fira Code` for numerical tabular data.
- [ ] Build the "Screener Table" (Dashboard Cockpit) configured to show specific deterministic columns: Asset (ticker/country), Status Badge, Valuation (`price_to_ncavps`, `margin_of_safety`), Survivability (`current_ratio`, `debt_to_equity`), The Dilution Law (`max_dilution_1y`), Freshness (`data_age_days`), and Signals (count of `green` vs `red` flags).
- [ ] Build the global filter bar above the table to rapidly filter the universe by Country, Status, and Risk flags.
- [ ] Build the "Individual Company Snapshot Page" (The Reason Card) that opens upon clicking a row in the Screener Table.
- [ ] Implement the Snapshot Page Header: Ticker, Name, Sector/Industry, `latest_fs_date`, and `fx_rate_used`.
- [ ] Implement the Snapshot Page Core Math section: Visual breakdown of `ncav_total_native` ➔ `ncav_per_share` ➔ `last_price` ➔ `margin_of_safety` featuring "Data Provenance" hover popovers showing exact SEC/yfinance line items.
- [ ] Implement the Snapshot Page Trend & Capital Allocation sections incorporating QoQ/HoH/YoY NCAV changes, recent dilution/buybacks, and max issue/buyback over 3 years.
- [ ] Implement the "Raw Financials Drawer" at the bottom of the Snapshot Page to lazily load and display the raw fetched arrays so humans can review statements independently.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

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
