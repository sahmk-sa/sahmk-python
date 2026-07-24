"""
Stream real-time market depth snapshots via WebSocket.

Usage:
    export SAHMK_API_KEY="your_api_key"
    python websocket_depth.py
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
logger = logging.getLogger("examples.websocket_depth")

client = SahmkClient(API_KEY)


async def run_stream(stop_event):
    snapshots = 0

    async def on_depth(msg):
        nonlocal snapshots
        if not msg.get("available", True):
            logger.warning(
                "depth unavailable symbol=%s message=%s",
                msg.get("symbol"),
                msg.get("message"),
            )
            return
        snapshots += 1
        logger.info(
            "depth symbol=%s bid=%s ask=%s spread=%s levels=%s total=%d",
            msg.get("symbol"),
            msg.get("best_bid"),
            msg.get("best_ask"),
            msg.get("spread"),
            msg.get("levels"),
            snapshots,
        )
        if stop_event.is_set():
            raise asyncio.CancelledError("stop requested")

    async def on_error(error):
        logger.warning("stream_error payload=%s", error)

    async def on_disconnect(reason):
        logger.warning("disconnected reason=%s", reason)

    async def on_reconnect(attempt):
        logger.info("reconnect attempt=%d", attempt)

    await client.stream_depth(
        SYMBOLS,
        on_depth=on_depth,
        on_error=on_error,
        on_disconnect=on_disconnect,
        on_reconnect=on_reconnect,
        levels=5,
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
