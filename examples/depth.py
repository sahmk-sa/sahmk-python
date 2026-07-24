"""
Fetch market depth (order book) for a symbol.

Usage:
    export SAHMK_API_KEY="your_api_key"
    python depth.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

depth = client.depth("2222", levels=5)

print("=== Market Depth: 2222 ===")
print(f"Session: {depth.session}")
print(f"Book state: {depth.book_state}")
print(f"Best bid/ask: {depth.best_bid} / {depth.best_ask}")
print(f"Spread: {depth.spread} ({depth.spread_bps} bps)")
print(f"Levels: {depth.levels} (entitled: {depth.entitled_levels})")
print(f"Updated: {depth.updated_at}")
print()

print("Bids:")
for level in depth.bids:
    print(
        f"  L{level.level}: {level.price} x {level.quantity} "
        f"(orders={level.order_count})"
    )

print("Asks:")
for level in depth.asks:
    print(
        f"  L{level.level}: {level.price} x {level.quantity} "
        f"(orders={level.order_count})"
    )
