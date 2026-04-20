# Task: Walter OS Market-Specific Hard Vetoes [DEPRECATED]

## Goal
[DEPRECATED] Expand the "Universal Vetoes" to include regional traps, like Keiretsu cross-holdings in Japan.

## Status: REJECTED
As of 2026-04-20, the decision was made to **not** implement complex market-specific veto logic or regional risk flagging. The project will maintain a strictly deterministic, fact-based approach, leaving "Risk Interpretation" to the human analyst.

## Done means
- [ ] Define the interface for market-specific vetoes extending the universal veto concept.
- [ ] Implement a specific regional veto (e.g., Japanese Keiretsu Cross-Holding Veto).
- [ ] Integrate market-specific vetoes into the main screening path.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- Core Universal Vetoes must remain the only "Hard" removal layer.
- Ensure Walter OS continues to flag data *health* without making *investment risk* judgments.
