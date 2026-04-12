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
summary = client.market_summary(index="TASI")
print("=== Market Summary ===")
print(f"Index: {summary.get('index', 'N/A')}")
print(f"TASI: {summary.get('index_value', 'N/A')}")
print(f"Change: {summary.get('index_change', 'N/A')} ({summary.get('index_change_percent', 'N/A')}%)")
print(f"Volume: {summary.get('total_volume', 'N/A')}")
print(f"Delayed: {summary.get('is_delayed', 'N/A')}")
print(f"Mood: {summary.get('market_mood', 'N/A')}")
print()

# Top gainers
print("=== Top Gainers ===")
result = client.gainers(limit=5, index="NOMUC")
for stock in result["gainers"]:
    print(f"  {stock['symbol']} {stock.get('name_en', '')}: +{stock.get('change_percent', 'N/A')}%")
print(f"Index: {result.get('index', 'N/A')} | Delayed: {result.get('is_delayed', 'N/A')}")
print()

# Top losers
print("=== Top Losers ===")
result = client.losers(limit=5)
for stock in result["losers"]:
    print(f"  {stock['symbol']} {stock.get('name_en', '')}: {stock.get('change_percent', 'N/A')}%")
print()

# Volume leaders
print("=== Volume Leaders ===")
result = client.volume_leaders(limit=5)
for stock in result["stocks"]:
    print(f"  {stock['symbol']} {stock.get('name_en', '')}: {stock.get('volume', 'N/A')}")
