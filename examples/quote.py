"""
Get a single stock quote from SAHMK API.

Usage:
    python quote.py
"""

import sys
import os

# Add parent directory to path so we can import sahmk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

# Get Aramco quote
quote = client.quote("2222")

print(f"Stock: {quote['name']} ({quote['symbol']})")
print(f"Price: {quote['last_price']} SAR")
print(f"Change: {quote['change']} ({quote['change_pct']})")
print(f"Volume: {quote.get('volume', 'N/A')}")
print(f"High: {quote.get('high', 'N/A')}")
print(f"Low: {quote.get('low', 'N/A')}")
