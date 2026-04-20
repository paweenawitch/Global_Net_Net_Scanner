# Task: UI Reason Card & Data Provenance

## Goal
Implement the high-fidelity Individual Company Snapshot View ("The Reason Card") to provide absolute transparency and "Data Provenance" for every investment candidate.

## Done means
- [ ] Implement the **Individual Company Snapshot Page** (Reason Card) as a drill-down/modal from the Screener Table.
- [ ] Implement **Screener Search & Filtering**: Real-time fuzzy search by ticker or name across the entire universe.
- [ ] Implement **Data Provenance Popovers**: Hover effects on financial figures showing exact source fields (e.g., "SEC 10-K CashAndCashEquivalentsAtCarryingValue").
- [ ] Implement **NCAV Trend Visualization**: UI indicator/chart showing the QoQ and YoY growth or burn of Net Current Assets.
- [ ] Implement **Raw Financials Drawer**: A lazily-loaded table showing the raw historical arrays for human verification.
- [ ] Ensure all financial math displayed in the UI is anchored to the deterministic domain models.
- [ ] `scripts/check.*` passes

## Constraints / must not change
- **Fact-Based UI**: The interface must remain strictly deterministic (numerical truth over qualitative judgment).
- **Zero Hallucination**: Provenance must link to actual stored data strings in the `financials_json` column.

## Scope
IN:
- React drill-down components.
- Client-side or server-side search logic.
- CSS visualizations for financial trends.
- Data lineage tooltips.

OUT:
- Regional Risk Flagging logic (removed per user decision).
- Predictive analysts or qualitative forecasting.

## Suggested files (optional)
- `interfaces/ui/src/App.jsx`
- `interfaces/ui/src/components/ReasonCard.jsx`
- `interfaces/api/main.py`
