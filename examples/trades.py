"""
Fetch recent live trade prints for a symbol (Pro+).

Usage:
    export SAHMK_API_KEY="your_api_key"
    python trades.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

trades = client.trades("2222", limit=10)

print("=== Live Trades: 2222 ===")
print(f"Updated: {trades.updated_at}")
print(f"Count: {trades.count}")
if trades.summary:
    print(
        f"Summary: qty={trades.summary.trade_quantity} "
        f"value={trades.summary.trade_value} "
        f"latest={trades.summary.latest_event_time}"
    )
print()

for event in trades.events:
    print(
        f"  {event.event_time}  {event.price} x {event.quantity} "
        f"(value={event.value})"
    )
