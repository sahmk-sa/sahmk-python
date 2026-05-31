"""
Get historical price data for a stock (plan-limited by interval/range).

Usage:
    python historical.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

# Get Aramco daily data for January 2026 (Starter+ supports 1d/1w/1m)
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

# Intraday example (plan-limited: 60m available on Pro+, 30m on Business+)
intraday = client.historical(
    "2222",
    from_date="2026-01-01",
    to_date="2026-01-03",
    interval="60m",
)
print(
    f"\nIntraday interval={intraday['interval']} bars={intraday['count']} "
    f"latest={intraday.get('metadata', {}).get('latest_bar_at')}"
)

# Weekly interval:
# result = client.historical("2222", from_date="2025-01-01", to_date="2025-06-30", interval="1w")

# If interval/range is outside your plan, API returns 403 PLAN_LIMIT.
