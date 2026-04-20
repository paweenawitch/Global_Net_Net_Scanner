# Task: Walter OS Global FX Normalization

## Goal
Establish a reliable Spot FX normalization utility to support cross-currency listings (e.g. US-listed foreign stocks) using Yahoo Finance with 24h JSON caching.

## Done means
- [x] Consolidate multiple FX providers into a single `YahooFxProvider`.
- [x] Implement 24h JSON caching to prevent API throttling.
- [x] Implement robust CNY/CNH fallback logic (Prefer CNY, fallback to CNH).
- [x] Harmonize interfaces (moving to `usd_per_ccy(currencies)`).
- [x] Update screening entry points to use the new provider.

## Constraints / must not change
- Pivot to **Spot Rates only**. Historical filing-date FX is discarded as it does not reflect realization value for a USD investor.
- Must fallback gracefully (USD=1.0) if network fails.

## Scope
IN:
- Spot FX fetching from Yahoo.
- CNY/CNH aliasing.
- 24h Local caching.

OUT:
- Historical FX database.
- Deterministic filing-date anchoring.

## Review Feedback
- **Provider Consolidation**: `infrastructure/sources/yahoo_fx_provider.py` successfully consolidates FX fetching into a single point of truth using `yfinance`.
- **Caching Logic**: Implemented 24h TTL caching based on file system `st_mtime` to stay within rate limits.
- **RMB Handling**: Robust CNY/CNH aliasing is handled both at fetch time (in `YahooFxProvider`) and via domain-level aliases in `domain/services/fx_utils.py`, ensuring consistent math regardless of source ticker.
- **Standardized Interface**: The `usd_per_ccy(currencies)` port is respected, allowing for seamless cross-currency conversions using the `convert_between` domain service.
- **Verification**: `tests/test_fx_utils.py` confirms that the conversion math and aliasing are accurate across multiple test cases.
