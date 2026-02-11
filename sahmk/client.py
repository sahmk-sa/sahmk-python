"""
SAHMK Python Client

A lightweight wrapper for the SAHMK Developer API.
https://sahmk.sa/developers/docs
"""

import json

import requests

BASE_URL = "https://app.sahmk.sa/api/v1"
WS_URL = "wss://app.sahmk.sa/ws/v1/stocks/"


class SahmkError(Exception):
    """Base exception for SAHMK API errors."""

    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class SahmkClient:
    """
    SAHMK Developer API client.

    Usage:
        client = SahmkClient("your_api_key")
        quote = client.quote("2222")
        print(quote["last_price"])
    """

    def __init__(self, api_key, base_url=None, timeout=30):
        """
        Initialize the client.

        Args:
            api_key: Your SAHMK API key (starts with shmk_live_)
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
                response=response,
            )

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except (ValueError, KeyError):
                detail = response.text
            raise SahmkError(
                f"API error {response.status_code}: {detail}",
                status_code=response.status_code,
                response=response,
            )

        return response.json()

    # -------------------------------------------------------------------------
    # Quotes
    # -------------------------------------------------------------------------

    def quote(self, symbol):
        """
        Get a real-time stock quote.

        Args:
            symbol: Stock symbol (e.g., "2222" for Aramco)

        Returns:
            dict with keys like name, last_price, change, change_pct, volume, etc.
        """
        return self._request("GET", f"/quote/{symbol}/")

    def quotes(self, symbols):
        """
        Get batch quotes for multiple stocks.

        Args:
            symbols: List of stock symbols (up to 50)

        Returns:
            list of quote dicts
        """
        if len(symbols) > 50:
            raise SahmkError("Maximum 50 symbols per batch request")
        return self._request(
            "GET", "/quotes/", params={"symbols": ",".join(symbols)}
        )

    # -------------------------------------------------------------------------
    # Historical
    # -------------------------------------------------------------------------

    def historical(self, symbol, period=None, start_date=None, end_date=None):
        """
        Get historical price data.

        Args:
            symbol: Stock symbol
            period: Shortcut — "1m", "3m", "6m", "1y", "5y"
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            list of OHLCV records
        """
        params = {}
        if period:
            params["period"] = period
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._request("GET", f"/historical/{symbol}/", params=params)

    # -------------------------------------------------------------------------
    # Market
    # -------------------------------------------------------------------------

    def market_summary(self):
        """Get market overview (TASI index, change, volume)."""
        return self._request("GET", "/market/summary/")

    def gainers(self):
        """Get top gaining stocks."""
        return self._request("GET", "/market/gainers/")

    def losers(self):
        """Get top losing stocks."""
        return self._request("GET", "/market/losers/")

    def volume_leaders(self):
        """Get stocks with highest volume."""
        return self._request("GET", "/market/volume/")

    def value_leaders(self):
        """Get stocks with highest traded value."""
        return self._request("GET", "/market/value/")

    def sectors(self):
        """Get sector performance."""
        return self._request("GET", "/market/sectors/")

    # -------------------------------------------------------------------------
    # Company Data
    # -------------------------------------------------------------------------

    def company(self, symbol):
        """Get company info (name, sector, description, etc.)."""
        return self._request("GET", f"/company/{symbol}/")

    def financials(self, symbol):
        """Get financial statements (income, balance sheet, cash flow)."""
        return self._request("GET", f"/financials/{symbol}/")

    def dividends(self, symbol):
        """Get dividend history."""
        return self._request("GET", f"/dividends/{symbol}/")

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    def events(self, symbol=None):
        """
        Get market events (earnings, dividends, IPOs).

        Args:
            symbol: Optional — filter events for a specific stock
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/events/", params=params)

    # -------------------------------------------------------------------------
    # WebSocket Streaming (Pro plan required)
    # -------------------------------------------------------------------------

    async def stream(self, symbols, on_quote=None, on_error=None):
        """
        Stream real-time quotes via WebSocket (Pro plan required).

        Args:
            symbols: List of stock symbols to subscribe to
            on_quote: Async callback for quote updates — on_quote(data)
            on_error: Async callback for errors — on_error(error_data)

        Usage:
            async def handle_quote(data):
                print(f"{data['symbol']}: {data['last_price']}")

            await client.stream(["2222", "1120"], on_quote=handle_quote)
        """
        try:
            import websockets
        except ImportError:
            raise SahmkError(
                "websockets package required for streaming. "
                "Install it with: pip install websockets"
            )

        url = f"{WS_URL}?api_key={self.api_key}"

        async with websockets.connect(url) as ws:
            # Wait for connected message
            msg = json.loads(await ws.recv())
            if msg.get("type") == "error":
                raise SahmkError(f"WebSocket error: {msg.get('message')}")

            # Subscribe to symbols (max 20 per call)
            for i in range(0, len(symbols), 20):
                batch = symbols[i : i + 20]
                await ws.send(
                    json.dumps({"type": "subscribe", "symbols": batch})
                )
                ack = json.loads(await ws.recv())
                if ack.get("type") == "error":
                    raise SahmkError(
                        f"Subscribe error: {ack.get('message')}"
                    )

            # Listen for updates
            async for message in ws:
                data = json.loads(message)

                if data.get("type") == "quote" and on_quote:
                    await on_quote(data.get("data", data))
                elif data.get("type") == "error" and on_error:
                    await on_error(data)
                elif data.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
