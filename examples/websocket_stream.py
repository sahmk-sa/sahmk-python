"""
Real-time stock price streaming via WebSocket.

Requires Pro plan or higher.

Usage:
    python websocket_stream.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")

client = SahmkClient(API_KEY)


async def on_quote(msg):
    """Called when a real-time quote update is received."""
    symbol = msg.get("symbol", "?")
    data = msg.get("data", {})
    price = data.get("price", "?")
    change = data.get("change_percent", "?")
    net_liq = data.get("liquidity", {}).get("net_value", "N/A")
    print(f"[LIVE] {symbol}: {price} SAR ({change}%) | Net Liquidity: {net_liq}")


async def on_error(error):
    """Called on WebSocket errors."""
    print(f"[ERROR] {error.get('message', error)}")


async def main():
    symbols = ["2222", "1120", "4191", "2010"]

    print(f"Streaming real-time quotes for: {', '.join(symbols)}")
    print("Press Ctrl+C to stop\n")

    try:
        await client.stream(symbols, on_quote=on_quote, on_error=on_error)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    asyncio.run(main())
