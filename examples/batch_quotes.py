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

# Batch quotes — up to 50 identifiers.
# Mix symbols and names/aliases (name/alias requires backend resolution support).
identifiers = ["2222", "الراجحي", "SABIC", "2010", "7010"]
result = client.quotes(identifiers)

print(f"{'Symbol':<10} {'Name':<25} {'Price':<10} {'Change %':<10}")
print("-" * 55)

for q in result["quotes"]:
    print(f"{q['symbol']:<10} {q.get('name_en', ''):<25} {q['price']:<10} {q['change_percent']:<10}")

if result.ambiguous:
    print("\nAmbiguous identifiers:", result.ambiguous)
if result.unknown:
    print("\nUnknown identifiers:", result.unknown)
