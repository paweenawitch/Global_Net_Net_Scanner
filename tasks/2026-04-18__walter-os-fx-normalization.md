# Task: Walter OS Global FX Normalization

## Goal
Establish a deterministic, filing-date-anchored FX normalization service in the infrastructure layer to support Walter OS globally.

## Done means
- [ ] Create `infrastructure/fx/fx_service.py` with caching/persistence.
- [ ] Ability to query exchange rate for `(base_currency, target_currency, filing_date)`.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- FX rates must strictly align with the filing end-date, not the current run date, to preserve determinism.
- Must fallback gracefully if historical FX missing, halting the pass rather than guessing.

## Scope
IN:
- Fetching historical FX data.
- Connecting FX service to `build_universe_service` or screening pipelines.

OUT:
- Live streaming FX.
- Speculating on currency hedges.

## Suggested files (optional)
- `infrastructure/fx/fx_service.py`
- `domain/models/currency.py`
