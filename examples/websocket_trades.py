"""
Stream real-time trade prints via WebSocket (Pro+).

Usage:
    export SAHMK_API_KEY="your_api_key"
    python websocket_trades.py
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import suppress

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sahmk import SahmkClient
from sahmk.client import SahmkError

API_KEY = os.environ.get("SAHMK_API_KEY", "your_api_key_here")
SYMBOLS = ["2222", "1120"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("examples.websocket_trades")

client = SahmkClient(API_KEY)


async def run_stream(stop_event):
    trades = 0
    snapshots = 0

    async def on_trade(msg):
        nonlocal trades
        trades += 1
        logger.info(
            "trade symbol=%s price=%s qty=%s value=%s session=%s total=%d",
            msg.get("symbol"),
            msg.get("price"),
            msg.get("quantity"),
            msg.get("value"),
            msg.get("market_session"),
            trades,
        )
        if stop_event.is_set():
            raise asyncio.CancelledError("stop requested")

    async def on_snapshot(msg):
        nonlocal snapshots
        snapshots += 1
        logger.info(
            "snapshot symbol=%s count=%s total_snapshots=%d",
            msg.get("symbol"),
            msg.get("count"),
            snapshots,
        )

    async def on_error(error):
        logger.warning("stream_error payload=%s", error)

    async def on_disconnect(reason):
        logger.warning("disconnected reason=%s", reason)

    async def on_reconnect(attempt):
        logger.info("reconnect attempt=%d", attempt)

    await client.stream_trades(
        SYMBOLS,
        on_trade=on_trade,
        on_snapshot=on_snapshot,
        on_error=on_error,
        on_disconnect=on_disconnect,
        on_reconnect=on_reconnect,
    )


async def main():
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop():
        logger.info("shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    task = asyncio.create_task(run_stream(stop_event))
    try:
        await task
    except (asyncio.CancelledError, SahmkError) as exc:
        logger.info("stream stopped: %s", exc)
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


if __name__ == "__main__":
    asyncio.run(main())
