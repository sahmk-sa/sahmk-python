"""
Get a single stock quote from SAHMK API.

Usage:
    python quote.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)


def print_quote(label, quote):
    print(f"\n{label}")
    print(f"Stock: {quote['name_en']} ({quote['symbol']})")
    print(f"Price: {quote['price']} SAR")
    print(f"Change: {quote['change']} ({quote['change_percent']}%)")
    print(f"Volume: {quote.get('volume', 'N/A')}")
    print(f"High: {quote.get('high', 'N/A')}")
    print(f"Low: {quote.get('low', 'N/A')}")
    print(f"Bid: {quote.get('bid', 'N/A')}")
    print(f"Ask: {quote.get('ask', 'N/A')}")

    liq = quote.get("liquidity", {})
    if liq:
        print(f"Net Liquidity: {liq.get('net_value', 'N/A')} SAR")

    if quote.resolution:
        print(f"Resolved by: {quote.resolution.matched_by}")
        print(f"Input => Symbol: {quote.requested_identifier} => {quote.resolved_symbol}")


# 1) Classic symbol usage (always supported)
quote_by_symbol = client.quote("2222")
print_quote("Quote by symbol", quote_by_symbol)

# 2) Name/alias usage (requires backend identifier-resolution support)
quote_by_name = client.quote("Aramco")
print_quote("Quote by name/alias", quote_by_name)
