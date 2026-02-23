"""
Get historical price data for a stock (Starter+ plan).

Usage:
    python historical.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

# Get Aramco data for January 2026
result = client.historical("2222", from_date="2026-01-01", to_date="2026-01-28")

records = result["data"]
print(f"Historical data for {result['symbol']} ({result['count']} records, interval: {result['interval']})")
print(f"{'Date':<15} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<15}")
print("-" * 70)

for record in records[-10:]:
    print(
        f"{record.get('date', ''):<15} "
        f"{record.get('open', ''):<10} "
        f"{record.get('high', ''):<10} "
        f"{record.get('low', ''):<10} "
        f"{record.get('close', ''):<10} "
        f"{record.get('volume', ''):<15}"
    )

# Weekly interval:
# result = client.historical("2222", from_date="2025-01-01", to_date="2025-06-30", interval="1w")
