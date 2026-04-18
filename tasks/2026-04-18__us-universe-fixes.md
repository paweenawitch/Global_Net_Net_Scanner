# Task: US Universe Dual-Class & ADR Fixes

## Goal
Fix structural issues in `application/build_universe_service.py` related to the US market, specifically deduplicating dual-class share structures and explicitly handling ADRs.

## Done means
- [ ] Identify and merge market caps for dual-class entities (e.g., BRK.A / BRK.B).
- [ ] Add explicit logic in `universe_schema.py` or parser to tag and filter ADRs.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- Global dedupe fallback logic (`_dedupe_global`) must remain robust for non-US markets.
- Output dataframe schema (`UniverseSchema` canonical columns) cannot change.

## Scope
IN:
- `build_universe_service.py` and potentially specific US `TickerSource` parsers.
- Handling duplicate fundamental ratios by retaining the primary voting share class while summing total enterprise value.

OUT:
- International market de-duplication rules.

## Suggested files (optional)
- `application/build_universe_service.py`
- `application/universe_schema.py`
