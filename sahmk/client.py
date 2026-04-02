"""
SAHMK Python Client

A lightweight wrapper for the SAHMK Developer API.
https://sahmk.sa/developers/docs
"""

import json
import logging

import requests

BASE_URL = "https://app.sahmk.sa/api/v1"
WS_URL = "wss://app.sahmk.sa/ws/v1/stocks/"

logger = logging.getLogger("sahmk")


class SahmkError(Exception):
    """Base exception for SAHMK API errors."""

    def __init__(self, message, status_code=None, error_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response = response


class SahmkClient:
    """
    SAHMK Developer API client.

    Usage:
        client = SahmkClient("your_api_key")
        quote = client.quote("2222")
        print(quote["price"])
    """

    def __init__(self, api_key, base_url=None, timeout=30):
        """
        Initialize the client.

        Args:
            api_key: Your SAHMK API key (starts with shmk_live_ or shmk_test_)
            base_url: Override the default API base URL
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_key = api_key
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

    def _request(self, method, endpoint, params=None):
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(
                method, url, params=params, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise SahmkError(f"Request failed: {e}")

        if response.status_code == 429:
            raise SahmkError(
                "Rate limit exceeded. Check X-RateLimit-Remaining header.",
                status_code=429,
                error_code="RATE_LIMIT",
                response=response,
            )

        if response.status_code != 200:
            try:
                body = response.json()
                err = body.get("error", {})
                code = err.get("code", "UNKNOWN")
                message = err.get("message", response.text)
            except (ValueError, KeyError):
                code = "UNKNOWN"
                message = response.text
            raise SahmkError(
                f"API error {response.status_code}: {message}",
                status_code=response.status_code,
                error_code=code,
                response=response,
            )

        return response.json()

    # -------------------------------------------------------------------------
    # Quotes
    # -------------------------------------------------------------------------

    def quote(self, symbol):
        """
        Get a stock quote.

        Args:
            symbol: Stock symbol (e.g., "2222" for Aramco)

        Returns:
            dict with keys: symbol, name, name_en, price, change,
            change_percent, volume, bid, ask, liquidity, etc.
        """
        return self._request("GET", f"/quote/{symbol}/")

    def quotes(self, symbols):
        """
        Get batch quotes for multiple stocks (Starter+ plan).

        Args:
            symbols: List of stock symbols (up to 50)

        Returns:
            dict with "quotes" list and "count"
        """
        if len(symbols) > 50:
            raise SahmkError("Maximum 50 symbols per batch request")
        return self._request(
            "GET", "/quotes/", params={"symbols": ",".join(symbols)}
        )

    # -------------------------------------------------------------------------
    # Historical
    # -------------------------------------------------------------------------

    def historical(self, symbol, from_date=None, to_date=None, interval=None):
        """
        Get historical OHLCV data (Starter+ plan).

        Args:
            symbol: Stock symbol
            from_date: Start date YYYY-MM-DD (default: 30 days ago)
            to_date: End date YYYY-MM-DD (default: today)
            interval: "1d", "1w", or "1m" (default: "1d")

        Returns:
            dict with "symbol", "interval", "from", "to", "count", and "data" list
        """
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if interval:
            params["interval"] = interval
        return self._request("GET", f"/historical/{symbol}/", params=params)

    # -------------------------------------------------------------------------
    # Market
    # -------------------------------------------------------------------------

    def market_summary(self):
        """Get market overview (TASI index, change, volume, market_mood)."""
        return self._request("GET", "/market/summary/")

    def gainers(self, limit=None):
        """
        Get top gaining stocks.

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            dict with "gainers" list and "count"
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/market/gainers/", params=params or None)

    def losers(self, limit=None):
        """
        Get top losing stocks.

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            dict with "losers" list and "count"
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/market/losers/", params=params or None)

    def volume_leaders(self, limit=None):
        """
        Get stocks with highest trading volume.

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            dict with "stocks" list and "count"
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/market/volume/", params=params or None)

    def value_leaders(self, limit=None):
        """
        Get stocks with highest trading value (SAR).

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            dict with "stocks" list and "count"
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/market/value/", params=params or None)

    def sectors(self):
        """
        Get sector performance.

        Returns:
            dict with "sectors" list and "count"
        """
        return self._request("GET", "/market/sectors/")

    # -------------------------------------------------------------------------
    # Company Data
    # -------------------------------------------------------------------------

    def company(self, symbol):
        """
        Get company info. Response varies by plan:
        Free (basic), Starter (fundamentals), Pro (technicals, valuation, analysts).
        """
        return self._request("GET", f"/company/{symbol}/")

    def financials(self, symbol):
        """Get financial statements (income, balance sheet, cash flow). Starter+ plan."""
        return self._request("GET", f"/financials/{symbol}/")

    def dividends(self, symbol):
        """Get dividend history and yield. Starter+ plan."""
        return self._request("GET", f"/dividends/{symbol}/")

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    def events(self, symbol=None, limit=None):
        """
        Get AI-generated stock event summaries (Pro+ plan).

        Args:
            symbol: Optional — filter events for a specific stock
            limit: Number of results (default: 20)

        Returns:
            dict with "events" list, "count", and "available_types"
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/events/", params=params or None)

    # -------------------------------------------------------------------------
    # WebSocket Streaming (Pro+ plan)
    # -------------------------------------------------------------------------

    async def stream(
        self,
        symbols,
        on_quote=None,
        on_error=None,
        on_disconnect=None,
        on_reconnect=None,
        ping_interval=30,
        max_reconnect_attempts=0,
        initial_reconnect_delay=1.0,
        max_reconnect_delay=60.0,
    ):
        """
        Stream real-time quotes via WebSocket (Pro+ plan).

        Supports automatic reconnection with exponential backoff. After a
        disconnect the client will reconnect and resubscribe to all symbols
        automatically.

        Args:
            symbols: List of stock symbols to subscribe to (max 20 per call,
                     max 60 per connection on Pro, 200 on Enterprise)
            on_quote: Async callback — on_quote(data) where data contains
                      symbol, timestamp, and quote fields (price, change, etc.)
            on_error: Async callback — on_error(error_data)
            on_disconnect: Async callback — on_disconnect(reason) called when
                           the connection drops. Receives a string reason.
            on_reconnect: Async callback — on_reconnect(attempt) called after
                          a successful reconnection. Receives the attempt number.
            ping_interval: Seconds between keep-alive pings (default: 30)
            max_reconnect_attempts: Maximum reconnection attempts. 0 means
                                    unlimited reconnection (default). Set to -1
                                    to disable reconnection entirely.
            initial_reconnect_delay: Initial delay in seconds before first
                                     reconnect attempt (default: 1.0)
            max_reconnect_delay: Maximum delay in seconds between reconnect
                                 attempts (default: 60.0)

        Usage:
            async def handle_quote(data):
                print(f"{data['symbol']}: {data['data']['price']}")

            await client.stream(["2222", "1120"], on_quote=handle_quote)
        """
        try:
            import websockets
        except ImportError:
            raise SahmkError(
                "websockets package required for streaming. "
                "Install it with: pip install websockets"
            )

        import asyncio

        reconnect_enabled = max_reconnect_attempts != -1
        attempt = 0
        delay = initial_reconnect_delay

        while True:
            try:
                await self._stream_connection(
                    symbols=symbols,
                    on_quote=on_quote,
                    on_error=on_error,
                    ping_interval=ping_interval,
                )
                return
            except SahmkError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reason = str(exc) or type(exc).__name__

                if on_disconnect:
                    try:
                        await on_disconnect(reason)
                    except Exception:
                        pass

                if not reconnect_enabled:
                    raise SahmkError(
                        f"WebSocket disconnected: {reason}"
                    )

                attempt += 1

                if max_reconnect_attempts > 0 and attempt > max_reconnect_attempts:
                    raise SahmkError(
                        f"WebSocket reconnection failed after "
                        f"{max_reconnect_attempts} attempts: {reason}"
                    )

                logger.info(
                    "WebSocket disconnected (%s), reconnecting in %.1fs "
                    "(attempt %d)...",
                    reason,
                    delay,
                    attempt,
                )

                await asyncio.sleep(delay)
                delay = min(delay * 2, max_reconnect_delay)

                if on_reconnect:
                    try:
                        await on_reconnect(attempt)
                    except Exception:
                        pass

    async def _stream_connection(
        self,
        symbols,
        on_quote=None,
        on_error=None,
        ping_interval=30,
    ):
        """Single WebSocket connection lifecycle: connect, subscribe, listen."""
        import asyncio
        import websockets

        url = f"{WS_URL}?api_key={self.api_key}"

        async with websockets.connect(url) as ws:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "error":
                raise SahmkError(f"WebSocket error: {msg.get('message')}")

            for i in range(0, len(symbols), 20):
                batch = symbols[i : i + 20]
                await ws.send(
                    json.dumps({"action": "subscribe", "symbols": batch})
                )
                ack = json.loads(await ws.recv())
                if ack.get("type") == "error":
                    raise SahmkError(
                        f"Subscribe error: {ack.get('message')}"
                    )

            async def _ping_loop():
                while True:
                    await asyncio.sleep(ping_interval)
                    try:
                        await ws.send(json.dumps({"action": "ping"}))
                    except Exception:
                        break

            ping_task = asyncio.create_task(_ping_loop())

            try:
                async for message in ws:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "quote" and on_quote:
                        await on_quote(data)
                    elif msg_type == "error":
                        if on_error:
                            await on_error(data)
                        else:
                            logger.warning(
                                "WebSocket error (unhandled): %s",
                                data.get("message", data),
                            )
            finally:
                ping_task.cancel()
