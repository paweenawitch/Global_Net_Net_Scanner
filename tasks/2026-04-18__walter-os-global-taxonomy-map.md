# Task: Walter OS Global Taxonomy Map

## Goal
Create a translation layer in the domain to map idiosyncratic global financial terms (IFRS, Local GAAP) to the canonical `UniverseSchema`.

## Done means
- [ ] Create `domain/translation/` module.
- [ ] Implement mappers for at least one foreign market (e.g., Japan or UK) to the `UniverseSchema`.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- The core screening math and thresholds must remain identical; only the data feeding into it is translated.
- Pure domain logic only (no side-effects).

## Scope
IN:
- `domain/translation` logic.
- Mapping rules for common global accounting terms into standard NCAV/ROIC inputs.

OUT:
- Automated fetching of the raw global filings (handled by infrastructure source parsers).

## Suggested files (optional)
- `domain/translation/mapper.py`
- `domain/translation/japan_gaap.py`
