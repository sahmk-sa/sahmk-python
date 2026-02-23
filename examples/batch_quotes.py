"""
Fetch multiple stock quotes in a single request (Starter+ plan).

Usage:
    python batch_quotes.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)

# Batch quotes — up to 50 symbols per request
symbols = ["2222", "1120", "4191", "2010", "1010"]
result = client.quotes(symbols)

print(f"{'Symbol':<10} {'Name':<25} {'Price':<10} {'Change %':<10}")
print("-" * 55)

for q in result["quotes"]:
    print(f"{q['symbol']:<10} {q.get('name_en', ''):<25} {q['price']:<10} {q['change_percent']:<10}")
