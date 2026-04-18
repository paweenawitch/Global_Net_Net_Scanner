import pytest
from domain.services.fx_utils import _ccy_alias, _normalize_rates, convert_between

def test_ccy_alias_normalization():
    assert _ccy_alias("rmb") == "CNY"
    assert _ccy_alias("RMB") == "CNY"
    assert _ccy_alias("CNH") == "CNY"
    assert _ccy_alias("jpy") == "JPY"
    assert _ccy_alias(None) is None
    assert _ccy_alias("") == ""

def test_normalize_rates():
    raw_rates = {"RMB": 0.14, "jpy": 0.0067, "HKD": 0.13, "INVALID": None}
    normalized = _normalize_rates(raw_rates)
    
    assert normalized.get("CNY") == 0.14
    assert normalized.get("JPY") == 0.0067
    assert normalized.get("HKD") == 0.13
    assert "INVALID" not in normalized

def test_convert_between_same_currency():
    # It should early exit and return the float amount
    fx_rates = {"JPY": 0.0067}
    assert convert_between(100.0, "JPY", "JPY", fx_rates) == 100.0
    assert convert_between(100.0, "jpy", "JPY", fx_rates) == 100.0

def test_convert_between_missing_inputs():
    fx_rates = {"JPY": 0.0067}
    assert convert_between(None, "JPY", "USD", fx_rates) is None
    assert convert_between(100.0, None, "USD", fx_rates) is None
    assert convert_between(100.0, "JPY", None, fx_rates) is None

def test_convert_to_usd():
    # 100 JPY @ 0.0067 USD/JPY = 0.67 USD
    fx_rates = {"JPY": 0.0067}
    result = convert_between(100, "JPY", "USD", fx_rates)
    assert result == pytest.approx(0.67, 1e-4)

def test_convert_cross_currency():
    # JPY -> USD -> HKD
    # 100 JPY -> 0.67 USD
    # 0.67 USD -> 0.67 / 0.13 HKD = 5.1538 HKD
    fx_rates = {
        "JPY": 0.0067,
        "HKD": 0.13
    }
    result = convert_between(100, "JPY", "HKD", fx_rates)
    assert result == pytest.approx(5.1538, 1e-4)

def test_convert_missing_rate():
    # If the currency is not in our rates, it returns None
    fx_rates = {"JPY": 0.0067}
    assert convert_between(100, "HKD", "USD", fx_rates) is None
    assert convert_between(100, "USD", "HKD", fx_rates) is None
