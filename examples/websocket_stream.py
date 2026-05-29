"""
Production-style WebSocket streaming example.

Shows:
- long-running stream process
- structured logging
- graceful shutdown (SIGINT/SIGTERM)
- reconnect/disconnect visibility
- automatic resubscribe behavior after reconnect

Usage:
    export SAHMK_API_KEY="your_api_key"
    python websocket_stream.py
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
SYMBOLS = ["2222", "1120", "4191", "2010"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("examples.websocket_stream")

client = SahmkClient(API_KEY)


class StreamStats:
    def __init__(self):
        self.quotes = 0
        self.errors = 0
        self.disconnects = 0
        self.reconnects = 0


async def run_stream(stop_event):
    stats = StreamStats()

    async def on_quote(msg):
        stats.quotes += 1
        symbol = msg.get("symbol", "?")
        data = msg.get("data", {})
        logger.info(
            "quote symbol=%s price=%s change_pct=%s total_quotes=%d",
            symbol,
            data.get("price"),
            data.get("change_percent"),
            stats.quotes,
        )

    async def on_error(error):
        stats.errors += 1
        logger.warning("stream_error count=%d payload=%s", stats.errors, error)

    async def on_disconnect(reason):
        stats.disconnects += 1
        logger.warning(
            "disconnected count=%d reason=%s",
            stats.disconnects,
            reason,
        )

    async def on_reconnect(attempt):
        stats.reconnects += 1
        logger.info(
            "reconnect attempt=%d reconnect_count=%d resubscribe=automatic",
            attempt,
            stats.reconnects,
        )

    stream_task = asyncio.create_task(
        client.stream(
            SYMBOLS,
            on_quote=on_quote,
            on_error=on_error,
            on_disconnect=on_disconnect,
            on_reconnect=on_reconnect,
        )
    )

    wait_task = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {stream_task, wait_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    if wait_task in done and stream_task and not stream_task.done():
        logger.info("shutdown_requested cancelling_stream")
        stream_task.cancel()
        with suppress(asyncio.CancelledError):
            await stream_task

    if stream_task in done and not stream_task.cancelled():
        exc = stream_task.exception()
        if exc:
            raise exc

    logger.info(
        "stream_stopped quotes=%d errors=%d disconnects=%d reconnects=%d",
        stats.quotes,
        stats.errors,
        stats.disconnects,
        stats.reconnects,
    )


async def main():
    if API_KEY == "your_api_key_here":
        logger.error("Missing SAHMK_API_KEY environment variable.")
        raise SystemExit(2)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    logger.info("starting_stream symbols=%s", ",".join(SYMBOLS))
    logger.info("stream_reconnect=enabled stream_resubscribe=automatic")
    logger.info("stop_with=Ctrl+C")

    try:
        await run_stream(stop_event)
    except SahmkError as exc:
        logger.error(
            "stream_failed message=%s status_code=%s error_code=%s",
            str(exc),
            getattr(exc, "status_code", None),
            getattr(exc, "error_code", None),
        )
        raise SystemExit(1)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
