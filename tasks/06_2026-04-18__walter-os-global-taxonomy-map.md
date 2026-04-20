# Task: Walter OS Global Taxonomy Verification

## Goal
Verify and refine the infrastructure-level mapping of idiosyncratic global financial terms (IFRS, Local GAAP) provided by `yfinance` to ensure they correctly populate our canonical domain models.

## Discussion Result
We decided that a standalone `domain/translation` module is redundant because `yfinance` already performs heavy-duty normalization across global exchanges. We will instead maintain and verify these mappings directly within the `infrastructure/sources/` layer.

## Done means
- [x] Audit `infrastructure/sources/yahoo_source.py` to ensure `_pick_row` synonyms cover common global variations (UK, Japan, HK).
- [x] Add unit tests for `YahooSource` mapping logic using mocked Yahoo payloads for different regions.
- [x] Document the "Trusted Schema" in `docs/architecture.md` (Yahoo as a normalized middleman).
- [x] `scripts/check.*` passes


## Constraints / must not change
- The domain core must remain source-agnostic (it receives `NcavRecord`, not raw Yahoo objects).
- No new domain modules should be created for this task.

## Scope
IN:
- `infrastructure/sources/yahoo_source.py` refinements.
- Testing mapping accuracy for international tickers.

OUT:
- Building a standalone mapping framework.
- Fetching raw EDINET/SEC filings directly.

## Suggested files (optional)
- `infrastructure/sources/yahoo_source.py`
- `tests/infrastructure/test_yahoo_mapping.py`

## Review Feedback
- **Synonym Coverage**: `infrastructure/sources/yahoo_source.py` has been audited and the `synonyms` dictionary in `_pick_row` successfully covers common global accounting term variations (e.g., `sharesoutstanding` mapping to `BasicSharesOutstanding`).
- **Standardized Mapping**: The "Yahoo as a Normalized Middleman" strategy is confirmed as a sound architectural decision, keeping the domain layer clean of translation logic.
- **Verification**: New unit tests in `tests/test_yahoo_mapping.py` verify that standard, synonym-based, and fuzzy matching all work correctly, including derivation logic (e.g., calculating Current Assets from Working Capital).
- **Execution**: All architecture and mapping tests passed (24/24) via `scripts/check.ps1`.
