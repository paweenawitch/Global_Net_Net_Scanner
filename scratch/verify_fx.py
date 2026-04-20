# scratch/verify_fx.py

import sys
import os
from pathlib import Path
import logging

# Add project root to sys.path
sys.path.append(os.getcwd())

from infrastructure.sources.yahoo_fx_provider import YahooFxProvider

def verify():
    logging.basicConfig(level=logging.INFO)
    cache_path = Path("cache/fx/latest_verify.json")
    
    # Remove old cache for clean test
    if cache_path.exists():
        cache_path.unlink()
        
    provider = YahooFxProvider(cache_file=cache_path)
    
    print("--- Fetching JPY, HKD, CNY, CNH ---")
    rates = provider.usd_per_ccy(["JPY", "HKD", "CNY", "CNH"])
    
    for ccy, rate in rates.items():
        print(f"{ccy}: {rate:.6f} USD per unit")
        
    print("\n--- Cache Content ---")
    if cache_path.exists():
        print(cache_path.read_text())
    else:
        print("Cache file NOT created!")

    # Check fallback
    print("\n--- Fallback Verification ---")
    # If we only ask for CNH, does it find it?
    rates2 = provider.usd_per_ccy(["CNH"])
    print(f"CNH from cache/fetch: {rates2.get('CNH')}")

if __name__ == "__main__":
    verify()
