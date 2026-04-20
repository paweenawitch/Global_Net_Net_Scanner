import pandas as pd
import pytest
from infrastructure.sources.yahoo_source import _extract_values, _pick_row

def test_pick_row_standard():
    df = pd.DataFrame(
        {"2023-01-01": [100, 50]},
        index=["Total Current Assets", "Total Liabilities"]
    )
    row = _pick_row(df, ["Total Current Assets"])
    assert row is not None
    assert row["2023-01-01"] == 100

def test_pick_row_synonyms():
    # Test that "Current Assets" maps to "Total Current Assets" logic
    df = pd.DataFrame(
        {"2023-01-01": [200]},
        index=["Current Assets"]
    )
    # The synonyms list for 'totalcurrentassets' includes 'currentassets'
    row = _pick_row(df, ["Total Current Assets"])
    assert row is not None
    assert row["2023-01-01"] == 200

def test_pick_row_fuzzy():
    # Test fuzzy matching (no spaces, case insensitive)
    df = pd.DataFrame(
        {"2023-01-01": [300]},
        index=["TOTAL_CURRENT_ASSET"]
    )
    row = _pick_row(df, ["Total Current Assets"])
    assert row is not None
    assert row["2023-01-01"] == 300

def test_extract_values_full():
    df = pd.DataFrame(
        {"2023-01-01": [1000, 400]},
        index=["Total Current Assets", "Total Liab"]
    )
    vals = _extract_values(df, "2023-01-01")
    assert vals["assets_current"] == 1000
    assert vals["liab_total"] == 400

def test_extract_values_derivation():
    # Test derivation: CA = Working Capital + CL
    df = pd.DataFrame(
        {"2023-01-01": [600, 200, 800]},
        index=["Working Capital", "Total Current Liabilities", "Total Liab"]
    )
    vals = _extract_values(df, "2023-01-01")
    # CA = 600 + 200 = 800
    assert vals["assets_current"] == 800
    assert vals["liab_total"] == 800

def test_extract_values_missing():
    df = pd.DataFrame(
        {"2023-01-01": [1000]},
        index=["Total Assets"] # No current assets info
    )
    vals = _extract_values(df, "2023-01-01")
    assert vals["assets_current"] is None
    assert vals["liab_total"] is None

def test_global_variations_japan():
    # Simulating a Japan-ish label if Yahoo didn't normalize it (though it usually does)
    # If Yahoo returns 'CurrentAssetsTotal' (sometimes seen in specific API versions)
    df = pd.DataFrame(
        {"2023-12-31": [5000, 2000]},
        index=["CurrentAssetsTotal", "LiabilitiesTotal"]
    )
    vals = _extract_values(df, "2023-12-31")
    assert vals["assets_current"] == 5000
    assert vals["liab_total"] == 2000
