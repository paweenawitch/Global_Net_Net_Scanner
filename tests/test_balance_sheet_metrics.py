import pytest
from domain.services.balance_sheet_metrics import (
    safe_float,
    get_balance_value,
    current_ratio,
    de_ratio,
    ncav_total_native,
    ncav_total_usd,
    compute_ncav_ps_from_period
)

def test_safe_float():
    assert safe_float(123) == 123.0
    assert safe_float("456.7") == 456.7
    assert safe_float("  89  ") == 89.0
    assert safe_float(None) is None
    assert safe_float("") is None
    assert safe_float("nan") is None
    assert safe_float("None") is None
    assert safe_float("invalid") is None

def test_get_balance_value():
    period_flat = {"assets_current": 100.0}
    assert get_balance_value(period_flat, "assets_current") == 100.0

    period_nested = {
        "balance": {
            "assets_current": {"val": 200.0, "unit": "USD"}
        }
    }
    assert get_balance_value(period_nested, "assets_current") == 200.0

    assert get_balance_value({}, "assets_current") is None
    assert get_balance_value(None, "assets_current") is None

def test_current_ratio():
    # Valid
    period = {
        "balance": {
            "assets_current": 200.0,
            "liab_current": 100.0
        }
    }
    assert current_ratio(period) == 2.0

    # Div by zero
    period_zero = {"balance": {"assets_current": 200.0, "liab_current": 0.0}}
    assert current_ratio(period_zero) is None

    # Missing
    period_missing = {"balance": {"assets_current": 200.0}}
    assert current_ratio(period_missing) is None

def test_de_ratio_with_explicit_equity():
    period = {
        "liab_total": 500.0,
        "equity": 1000.0
    }
    assert de_ratio(period) == 0.5

def test_de_ratio_derived_equity():
    period = {
        "assets_total": 2000.0,
        "liab_total": 500.0
    }
    # Equity = 2000 - 500 = 1500
    # D/E = 500 / 1500 = 1/3
    assert de_ratio(period) == pytest.approx(1/3, rel=1e-4)

def test_de_ratio_zero_equity():
    period = {
        "assets_total": 1000.0,
        "liab_total": 1000.0
    }
    assert de_ratio(period) is None

def test_ncav_total_native():
    period = {
        "assets_current": 1500.0,
        "liab_total": 500.0
    }
    assert ncav_total_native(period) == 1000.0

def test_ncav_total_native_fallback_total_assets():
    # Missing current assets, falls back to total assets
    period = {
        "assets_total": 2000.0,
        "liab_total": 500.0
    }
    assert ncav_total_native(period) == 1500.0

def test_compute_ncav_ps():
    period = {
        "assets_current": 1500.0,
        "liab_total": 500.0
    }
    # NCAV = 1000, shares = 100 -> NCAV/ps = 10
    assert compute_ncav_ps_from_period(period, 100.0) == 10.0

    # Handles zero shares implicitly
    assert compute_ncav_ps_from_period(period, 0.0) is None
    assert compute_ncav_ps_from_period(period, None) is None
