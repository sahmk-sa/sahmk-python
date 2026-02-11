"""
Get historical price data for a stock.

Usage:
    python historical.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

# Get last 3 months of Aramco data
data = client.historical("2222", period="3m")

print(f"Historical data for 2222 ({len(data)} records)")
print(f"{'Date':<15} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<15}")
print("-" * 70)

# Show the last 10 records
for record in data[-10:]:
    print(
        f"{record.get('date', ''):<15} "
        f"{record.get('open', ''):<10} "
        f"{record.get('high', ''):<10} "
        f"{record.get('low', ''):<10} "
        f"{record.get('close', ''):<10} "
        f"{record.get('volume', ''):<15}"
    )

# You can also use custom date ranges:
# data = client.historical("2222", start_date="2025-01-01", end_date="2025-06-30")
