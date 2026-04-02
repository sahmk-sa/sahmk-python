"""
SAHMK Python Client

A lightweight wrapper for the SAHMK Developer API.
https://sahmk.sa/developers/docs
"""

import json
import logging
import time

import requests

BASE_URL = "https://app.sahmk.sa/api/v1"
WS_URL = "wss://app.sahmk.sa/ws/v1/stocks/"

logger = logging.getLogger("sahmk")

_RETRIABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class SahmkError(Exception):
    """Base exception for SAHMK API errors."""

    def __init__(self, message, status_code=None, error_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response = response


class SahmkRateLimitError(SahmkError):
    """Raised when the API returns 429 Too Many Requests.

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header),
                     or None if the header was not present.
        rate_limit: Daily request limit (from X-RateLimit-Limit), or None.
        rate_remaining: Remaining requests (from X-RateLimit-Remaining), or None.
        rate_reset: Reset timestamp string (from X-RateLimit-Reset), or None.
    """

    def __init__(
        self,
        message,
        response=None,
        retry_after=None,
        rate_limit=None,
        rate_remaining=None,
        rate_reset=None,
    ):
        super().__init__(
            message,
            status_code=429,
            error_code="RATE_LIMIT",
            response=response,
        )
        self.retry_after = retry_after
        self.rate_limit = rate_limit
        self.rate_remaining = rate_remaining
        self.rate_reset = rate_reset


class SahmkClient:
    """
    SAHMK Developer API client.

    Usage:
        client = SahmkClient("your_api_key")
        quote = client.quote("2222")
        print(quote["price"])
    """

    def __init__(
        self,
        api_key,
        base_url=None,
        timeout=30,
        retries=3,
        backoff_factor=0.5,
        retry_on_timeout=True,
    ):
        """
        Initialize the client.

        Args:
            api_key: Your SAHMK API key (starts with shmk_live_ or shmk_test_)
            base_url: Override the default API base URL
            timeout: Request timeout in seconds (default: 30)
            retries: Max retry attempts for transient failures — 429 and 5xx.
                     Set to 0 to disable retries. (default: 3)
            backoff_factor: Multiplier for exponential backoff between retries.
                            Delay = backoff_factor * (2 ** attempt), so with the
                            default 0.5 the delays are 0.5s, 1s, 2s. (default: 0.5)
            retry_on_timeout: Whether to retry on request timeouts. (default: True)
        """
        self.api_key = api_key
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.retry_on_timeout = retry_on_timeout
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

    def _request(self, method, endpoint, params=None):
        """Make an API request with automatic retries for transient failures."""
        url = f"{self.base_url}{endpoint}"
        last_exc = None

        for attempt in range(1 + self.retries):
            try:
                response = self.session.request(
                    method, url, params=params, timeout=self.timeout
                )
            except requests.Timeout as e:
                last_exc = SahmkError(f"Request timed out: {e}")
                if self.retry_on_timeout and attempt < self.retries:
                    self._backoff(attempt)
                    continue
                raise last_exc
            except requests.RequestException as e:
                raise SahmkError(f"Request failed: {e}")

            if response.status_code == 429:
                last_exc = self._build_rate_limit_error(response)
                if attempt < self.retries:
                    wait = self._rate_limit_wait(response, attempt)
                    logger.info(
                        "Rate limited (429), retrying in %.1fs (attempt %d/%d)...",
                        wait,
                        attempt + 1,
                        self.retries,
                    )
                    time.sleep(wait)
                    continue
                raise last_exc

            if response.status_code in _RETRIABLE_STATUS_CODES:
                last_exc = self._build_api_error(response)
                if attempt < self.retries:
                    wait = self.backoff_factor * (2 ** attempt)
                    logger.info(
                        "Server error (%d), retrying in %.1fs (attempt %d/%d)...",
                        response.status_code,
                        wait,
                        attempt + 1,
                        self.retries,
                    )
                    time.sleep(wait)
                    continue
                raise last_exc

            if response.status_code != 200:
                raise self._build_api_error(response)

            return response.json()

        raise last_exc  # pragma: no cover

    def _backoff(self, attempt):
        """Sleep for exponential backoff duration."""
        wait = self.backoff_factor * (2 ** attempt)
        logger.info(
            "Request failed, retrying in %.1fs (attempt %d/%d)...",
            wait,
            attempt + 1,
            self.retries,
        )
        time.sleep(wait)

    @staticmethod
    def _build_rate_limit_error(response):
        """Build a SahmkRateLimitError from a 429 response."""
        headers = response.headers
        retry_after = None
        raw = headers.get("Retry-After")
        if raw:
            try:
                retry_after = float(raw)
            except (ValueError, TypeError):
                pass

        def _header_int(name):
            val = headers.get(name)
            if val:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
            return None

        return SahmkRateLimitError(
            "Rate limit exceeded.",
            response=response,
            retry_after=retry_after,
            rate_limit=_header_int("X-RateLimit-Limit"),
            rate_remaining=_header_int("X-RateLimit-Remaining"),
            rate_reset=headers.get("X-RateLimit-Reset"),
        )

    @staticmethod
    def _build_api_error(response):
        """Build a SahmkError from a non-200 response."""
        try:
            body = response.json()
            err = body.get("error", {})
            code = err.get("code", "UNKNOWN")
            message = err.get("message", response.text)
        except (ValueError, KeyError):
            code = "UNKNOWN"
            message = response.text
        return SahmkError(
            f"API error {response.status_code}: {message}",
            status_code=response.status_code,
            error_code=code,
            response=response,
        )

    def _rate_limit_wait(self, response, attempt):
        """Determine wait time for a 429 response, preferring Retry-After header."""
        raw = response.headers.get("Retry-After")
        if raw:
            try:
                return float(raw)
            except (ValueError, TypeError):
                pass
        return self.backoff_factor * (2 ** attempt)

    # -------------------------------------------------------------------------
    # Quotes
    # -------------------------------------------------------------------------

    def quote(self, symbol):
        """
        Get a stock quote.

        Args:
            symbol: Stock symbol (e.g., "2222" for Aramco)

        Returns:
            Quote object (supports dict-style access via [] for backwards compat)
        """
        from .models import Quote
        data = self._request("GET", f"/quote/{symbol}/")
        return Quote.from_dict(data)

    def quotes(self, symbols):
        """
        Get batch quotes for multiple stocks (Starter+ plan).

        Args:
            symbols: List of stock symbols (up to 50)

        Returns:
            BatchQuotesResponse with .quotes list and .count
        """
        from .models import BatchQuotesResponse
        if len(symbols) > 50:
            raise SahmkError("Maximum 50 symbols per batch request")
        data = self._request(
            "GET", "/quotes/", params={"symbols": ",".join(symbols)}
        )
        return BatchQuotesResponse.from_dict(data)

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
            HistoricalResponse with .data list of OHLCV objects
        """
        from .models import HistoricalResponse
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if interval:
            params["interval"] = interval
        data = self._request("GET", f"/historical/{symbol}/", params=params)
        return HistoricalResponse.from_dict(data)

    # -------------------------------------------------------------------------
    # Market
    # -------------------------------------------------------------------------

    def market_summary(self):
        """
        Get market overview (TASI index, change, volume, market_mood).

        Returns:
            MarketSummary object
        """
        from .models import MarketSummary
        data = self._request("GET", "/market/summary/")
        return MarketSummary.from_dict(data)

    def gainers(self, limit=None):
        """
        Get top gaining stocks.

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        params = {}
        if limit is not None:
            params["limit"] = limit
        data = self._request("GET", "/market/gainers/", params=params or None)
        return MarketMoversResponse.from_dict(data, list_key="gainers")

    def losers(self, limit=None):
        """
        Get top losing stocks.

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        params = {}
        if limit is not None:
            params["limit"] = limit
        data = self._request("GET", "/market/losers/", params=params or None)
        return MarketMoversResponse.from_dict(data, list_key="losers")

    def volume_leaders(self, limit=None):
        """
        Get stocks with highest trading volume.

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        params = {}
        if limit is not None:
            params["limit"] = limit
        data = self._request("GET", "/market/volume/", params=params or None)
        return MarketMoversResponse.from_dict(data, list_key="stocks")

    def value_leaders(self, limit=None):
        """
        Get stocks with highest trading value (SAR).

        Args:
            limit: Number of results (default: 10, max: 50)

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        params = {}
        if limit is not None:
            params["limit"] = limit
        data = self._request("GET", "/market/value/", params=params or None)
        return MarketMoversResponse.from_dict(data, list_key="stocks")

    def sectors(self):
        """
        Get sector performance.

        Returns:
            SectorsResponse with .sectors list
        """
        from .models import SectorsResponse
        data = self._request("GET", "/market/sectors/")
        return SectorsResponse.from_dict(data)

    # -------------------------------------------------------------------------
    # Company Data
    # -------------------------------------------------------------------------

    def company(self, symbol):
        """
        Get company info. Response varies by plan:
        Free (basic), Starter (fundamentals), Pro (technicals, valuation, analysts).

        Returns:
            Company object
        """
        from .models import Company as CompanyModel
        data = self._request("GET", f"/company/{symbol}/")
        return CompanyModel.from_dict(data)

    def financials(self, symbol):
        """
        Get financial statements (income, balance sheet, cash flow). Starter+ plan.

        Returns:
            FinancialsResponse object
        """
        from .models import FinancialsResponse
        data = self._request("GET", f"/financials/{symbol}/")
        return FinancialsResponse.from_dict(data)

    def dividends(self, symbol):
        """
        Get dividend history and yield. Starter+ plan.

        Returns:
            DividendsResponse object
        """
        from .models import DividendsResponse
        data = self._request("GET", f"/dividends/{symbol}/")
        return DividendsResponse.from_dict(data)

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
            EventsResponse with .events list
        """
        from .models import EventsResponse
        params = {}
        if symbol:
            params["symbol"] = symbol
        if limit is not None:
            params["limit"] = limit
        data = self._request("GET", "/events/", params=params or None)
        return EventsResponse.from_dict(data)

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
