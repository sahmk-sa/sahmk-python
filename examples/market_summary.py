"""
Get market overview — index, gainers, losers, volume leaders.

Usage:
    python market_summary.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

# Market overview
summary = client.market_summary()
print("=== Market Summary ===")
print(f"TASI: {summary.get('index_value', 'N/A')}")
print(f"Change: {summary.get('index_change', 'N/A')} ({summary.get('index_change_pct', 'N/A')})")
print()

# Top gainers
print("=== Top Gainers ===")
gainers = client.gainers()
for stock in gainers[:5]:
    print(f"  {stock['symbol']} {stock['name']}: {stock.get('change_pct', 'N/A')}")
print()

# Top losers
print("=== Top Losers ===")
losers = client.losers()
for stock in losers[:5]:
    print(f"  {stock['symbol']} {stock['name']}: {stock.get('change_pct', 'N/A')}")
print()

# Volume leaders
print("=== Volume Leaders ===")
volume = client.volume_leaders()
for stock in volume[:5]:
    print(f"  {stock['symbol']} {stock['name']}: {stock.get('volume', 'N/A')}")
