"""
SAHMK Python Client

A lightweight wrapper for the SAHMK Developer API.
https://sahmk.sa/developers/docs
"""

import json
import logging
import random
import re
import time

import requests

BASE_URL = "https://api.sahmk.sa/api/v1"
WS_URL = "wss://api.sahmk.sa/ws/v1/stocks/"
DEPTH_WS_URL = "wss://api.sahmk.sa/ws/v1/market/depth/"
TRADES_WS_URL = "wss://api.sahmk.sa/ws/v1/market/trades/"

logger = logging.getLogger("sahmk")

_RETRIABLE_STATUS_CODES = frozenset({500, 502, 503, 504})
_MARKET_INDEX_ALIASES = {"NOMUC": "NOMU"}
_VALID_MARKET_INDEXES = frozenset({"TASI", "NOMU"})
_WS_AUTH_CLOSE_CODE = 4401
_WS_ENTITLEMENT_CLOSE_CODE = 4403
_DEFAULT_WS_MAX_SYMBOLS_PER_CALL = 20
_DEPTH_LEVELS_MIN = 1
_DEPTH_LEVELS_MAX = 20
_TRADES_LIMIT_MIN = 1
_TRADES_LIMIT_MAX = 200
_TRADES_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Canonical historical intervals, then the legacy aliases the API still accepts.
# Note "1m" is one MONTH (alias of "1mo"); one-minute bars are "1min".
HISTORICAL_INTERVALS = ("1min", "5min", "15min", "30min", "60min", "1d", "1w", "1mo")
HISTORICAL_INTERVAL_ALIASES = {"30m": "30min", "60m": "60min", "1m": "1mo"}


class SahmkError(Exception):
    """Base exception for SAHMK API errors."""

    def __init__(
        self, message, status_code=None, error_code=None, response=None, errors=None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response = response
        # Per-field validation messages, when the API sends them (error.errors).
        self.errors = errors


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


class SahmkInvalidIndexError(SahmkError):
    """Raised when an invalid market index is supplied or returned by the API."""

    def __init__(self, message, response=None):
        super().__init__(
            message,
            status_code=400,
            error_code="INVALID_INDEX",
            response=response,
        )


class SahmkIdentifierResolutionError(SahmkError):
    """Base exception for identifier-resolution failures."""

    def __init__(
        self,
        message,
        status_code=None,
        error_code=None,
        response=None,
        identifier=None,
        details=None,
    ):
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
            response=response,
        )
        self.identifier = identifier
        self.details = details or {}


class SahmkAmbiguousIdentifierError(SahmkIdentifierResolutionError):
    """Raised when the input maps to multiple possible stocks."""

    def __init__(
        self,
        message,
        response=None,
        identifier=None,
        candidates=None,
        details=None,
        status_code=400,
        error_code="AMBIGUOUS_IDENTIFIER",
    ):
        merged_details = dict(details or {})
        if candidates is not None:
            merged_details.setdefault("candidates", candidates)
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
            response=response,
            identifier=identifier,
            details=merged_details,
        )
        self.candidates = merged_details.get("candidates", [])


class SahmkUnknownIdentifierError(SahmkIdentifierResolutionError):
    """Raised when an identifier cannot be resolved to any stock."""

    def __init__(
        self,
        message,
        response=None,
        identifier=None,
        details=None,
        status_code=404,
        error_code="UNKNOWN_IDENTIFIER",
    ):
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
            response=response,
            identifier=identifier,
            details=details,
        )


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

    def _request(self, method, endpoint, params=None, json_body=None):
        """Make an API request with automatic retries for transient failures.

        Reads (GET) retry on 429, 5xx, and timeouts. Writes retry only on 429,
        which the API returns before running the handler. A write that timed
        out or hit a 5xx may already have been applied, so it is raised to the
        caller instead of being sent again.
        """
        url = f"{self.base_url}{endpoint}"
        last_exc = None
        is_read = str(method).upper() == "GET"
        request_kwargs = {"params": params, "timeout": self.timeout}
        if json_body is not None:
            request_kwargs["json"] = json_body

        for attempt in range(1 + self.retries):
            try:
                response = self.session.request(method, url, **request_kwargs)
            except requests.Timeout as e:
                last_exc = SahmkError(f"Request timed out: {e}")
                if is_read and self.retry_on_timeout and attempt < self.retries:
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
                if is_read and attempt < self.retries:
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

            if not 200 <= response.status_code < 300:
                raise self._build_api_error(response)

            if response.status_code == 204 or not response.content:
                return None

            try:
                return response.json()
            except (ValueError, TypeError) as e:
                raise SahmkError(
                    f"Unexpected non-JSON response: {e}",
                    status_code=response.status_code,
                    response=response,
                )

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
        details = {}
        field_errors = None
        try:
            body = response.json()
            err = body.get("error")
            if not isinstance(err, dict):
                # Portfolio endpoints send the error at the top level:
                # {"success": false, "code": ..., "message"?: ..., "errors"?: {...}}
                err = body if "code" in body else {}
            code = err.get("code") or "UNKNOWN"
            if isinstance(err.get("details"), dict):
                details = err.get("details")
            if isinstance(err.get("errors"), (dict, list)) and err.get("errors"):
                field_errors = err.get("errors")
            message = err.get("message") or (code if field_errors else response.text)
        except (ValueError, KeyError, AttributeError):
            code = "UNKNOWN"
            message = response.text
        if response.status_code == 400 and code == "INVALID_INDEX":
            return SahmkInvalidIndexError(
                f"Invalid market index: {message}",
                response=response,
            )
        identifier = details.get("identifier") or details.get("input")
        if code in {"AMBIGUOUS_IDENTIFIER", "IDENTIFIER_AMBIGUOUS"}:
            candidates = details.get("candidates", [])
            candidate_text = ""
            if candidates:
                shown = candidates[:5]
                candidate_text = f" Candidates: {shown}"
            return SahmkAmbiguousIdentifierError(
                f"Ambiguous identifier '{identifier or '?'}': {message}.{candidate_text}",
                response=response,
                identifier=identifier,
                candidates=candidates,
                details=details,
                status_code=response.status_code,
                error_code=code,
            )
        if code in {"UNKNOWN_IDENTIFIER", "IDENTIFIER_NOT_FOUND", "INVALID_SYMBOL"}:
            return SahmkUnknownIdentifierError(
                f"Unknown identifier '{identifier or '?'}': {message}",
                response=response,
                identifier=identifier,
                details=details,
                status_code=response.status_code,
                error_code=code,
            )
        if field_errors is not None:
            message = f"{message} {field_errors}" if message else str(field_errors)
        return SahmkError(
            f"API error {response.status_code}: {message}",
            status_code=response.status_code,
            error_code=code,
            response=response,
            errors=field_errors,
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

    @staticmethod
    def _normalize_market_index(index):
        """Normalize/validate market index query parameter."""
        if index is None:
            return None
        normalized = str(index).strip().upper()
        normalized = _MARKET_INDEX_ALIASES.get(normalized, normalized)
        if normalized not in _VALID_MARKET_INDEXES:
            raise SahmkInvalidIndexError(
                "Index must be one of: TASI, NOMU (NOMUC is accepted as NOMU)."
            )
        return normalized

    def _market_params(self, limit=None, index=None):
        """Build validated query params for market endpoints."""
        params = {}
        if limit is not None:
            params["limit"] = limit
        normalized_index = self._normalize_market_index(index)
        if normalized_index is not None:
            params["index"] = normalized_index
        return params or None

    @staticmethod
    def _validate_limit_offset(limit, offset):
        """Validate shared pagination arguments."""
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer greater than 0")
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError("offset must be an integer greater than or equal to 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

    def _companies_params(self, search=None, market=None, limit=100, offset=0):
        """Build validated query params for the company directory endpoint."""
        self._validate_limit_offset(limit=limit, offset=offset)
        params = {"limit": limit, "offset": offset}
        if search is not None:
            params["search"] = search
        normalized_market = self._normalize_market_index(market)
        if normalized_market is not None:
            params["market"] = normalized_market
        return params

    # -------------------------------------------------------------------------
    # Quotes
    # -------------------------------------------------------------------------

    def quote(self, identifier):
        """
        Get a stock quote by symbol or resolvable identifier.

        Args:
            identifier: Stock symbol, Arabic name, English name, or alias
                        (e.g., "2222", "أرامكو السعودية", "Aramco")

        Returns:
            Quote object (supports dict-style access via [] for backwards compat)
        """
        from .models import Quote
        data = self._request("GET", f"/quote/{identifier}/")
        return Quote.from_dict(data)

    @staticmethod
    def _is_legacy_quotes_param_error(exc):
        """Detect old-backend validation errors when identifiers param is unknown."""
        if not isinstance(exc, SahmkError) or exc.status_code != 400:
            return False
        if exc.error_code in {
            "VALIDATION",
            "MISSING_SYMBOLS",
            "MISSING_PARAMETER",
            "UNKNOWN_PARAMETER",
        }:
            return True
        return "symbols" in str(exc).lower()

    def quotes(self, identifiers):
        """
        Get batch quotes for multiple stocks (Starter+ plan).

        Args:
            identifiers: List of symbols/names/aliases (up to 50). Existing
                         symbol-only usage remains fully supported.

        Returns:
            BatchQuotesResponse with .quotes list and .count
        """
        from .models import BatchQuotesResponse
        if isinstance(identifiers, str):
            identifiers = [identifiers]
        if not identifiers:
            raise ValueError("At least one symbol is required")
        if len(identifiers) > 50:
            raise SahmkError("Maximum 50 symbols per batch request")
        joined = ",".join(str(identifier) for identifier in identifiers)

        # Prefer the new backend contract first. If the backend is older and
        # rejects `identifiers`, transparently fall back to `symbols`.
        try:
            data = self._request(
                "GET",
                "/quotes/",
                params={"identifiers": joined},
            )
        except SahmkError as exc:
            if not self._is_legacy_quotes_param_error(exc):
                raise
            data = self._request("GET", "/quotes/", params={"symbols": joined})
        return BatchQuotesResponse.from_dict(data)

    # -------------------------------------------------------------------------
    # Historical
    # -------------------------------------------------------------------------

    def historical(
        self, symbol, from_date=None, to_date=None, interval=None, limit=None, offset=None
    ):
        """
        Get historical OHLCV data (Starter+ plan).

        Args:
            symbol: Stock symbol
            from_date: Start date YYYY-MM-DD (default: 30 days ago)
            to_date: End date YYYY-MM-DD (default: today)
            interval: One of "1min", "5min", "15min", "30min", "60min", "1d",
                      "1w", "1mo" (default: "1d"). Legacy aliases "30m",
                      "60m", and "1m" are still accepted; "1m" means one
                      month, not one minute. Intraday intervals and date
                      windows depend on your plan.
            limit: Optional max bars to return (backend default 500, max 2000)
            offset: Optional bars to skip from the start of the
                    chronologically ordered result (default 0)

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
        if limit is not None:
            params["limit"] = self._positive_int(limit, "limit")
        if offset is not None:
            if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                raise ValueError("offset must be a non-negative integer")
            params["offset"] = offset
        data = self._request("GET", f"/historical/{symbol}/", params=params)
        return HistoricalResponse.from_dict(data)

    # -------------------------------------------------------------------------
    # Market
    # -------------------------------------------------------------------------

    def market_summary(self, index=None):
        """
        Get market overview (TASI index, change, volume, market_mood).

        Args:
            index: Optional market index ("TASI" or "NOMU"). "NOMUC" alias
                   is accepted and normalized to "NOMU".

        Returns:
            MarketSummary object
        """
        from .models import MarketSummary
        data = self._request(
            "GET",
            "/market/summary/",
            params=self._market_params(index=index),
        )
        return MarketSummary.from_dict(data)

    def gainers(self, limit=None, index=None):
        """
        Get top gaining stocks.

        Args:
            limit: Number of results (default: 10, max: 50)
            index: Optional market index ("TASI" or "NOMU"). "NOMUC" alias
                   is accepted and normalized to "NOMU".

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        data = self._request(
            "GET",
            "/market/gainers/",
            params=self._market_params(limit=limit, index=index),
        )
        return MarketMoversResponse.from_dict(data, list_key="gainers")

    def losers(self, limit=None, index=None):
        """
        Get top losing stocks.

        Args:
            limit: Number of results (default: 10, max: 50)
            index: Optional market index ("TASI" or "NOMU"). "NOMUC" alias
                   is accepted and normalized to "NOMU".

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        data = self._request(
            "GET",
            "/market/losers/",
            params=self._market_params(limit=limit, index=index),
        )
        return MarketMoversResponse.from_dict(data, list_key="losers")

    def volume_leaders(self, limit=None, index=None):
        """
        Get stocks with highest trading volume.

        Args:
            limit: Number of results (default: 10, max: 50)
            index: Optional market index ("TASI" or "NOMU"). "NOMUC" alias
                   is accepted and normalized to "NOMU".

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        data = self._request(
            "GET",
            "/market/volume/",
            params=self._market_params(limit=limit, index=index),
        )
        return MarketMoversResponse.from_dict(data, list_key="stocks")

    def value_leaders(self, limit=None, index=None):
        """
        Get stocks with highest trading value (SAR).

        Args:
            limit: Number of results (default: 10, max: 50)
            index: Optional market index ("TASI" or "NOMU"). "NOMUC" alias
                   is accepted and normalized to "NOMU".

        Returns:
            MarketMoversResponse with .stocks list
        """
        from .models import MarketMoversResponse
        data = self._request(
            "GET",
            "/market/value/",
            params=self._market_params(limit=limit, index=index),
        )
        return MarketMoversResponse.from_dict(data, list_key="stocks")

    def sectors(self, index=None):
        """
        Get sector performance.

        Args:
            index: Optional market index ("TASI" or "NOMU"). "NOMUC" alias
                   is accepted and normalized to "NOMU".

        Returns:
            SectorsResponse with .sectors list
        """
        from .models import SectorsResponse
        data = self._request(
            "GET",
            "/market/sectors/",
            params=self._market_params(index=index),
        )
        return SectorsResponse.from_dict(data)

    def depth(self, symbol, levels=None):
        """
        Get market depth (order book) for a symbol.

        Args:
            symbol: Stock symbol (e.g., "2222")
            levels: Optional number of book levels to request (1-20).
                    Backend default is 5; entitlement may cap below the request.

        Returns:
            MarketDepth object with bids/asks ladders and book metrics
        """
        from .models import MarketDepth
        params = {}
        normalized_levels = self._normalize_depth_levels(levels)
        if normalized_levels is not None:
            params["levels"] = normalized_levels
        data = self._request(
            "GET",
            f"/market/depth/{symbol}/",
            params=params or None,
        )
        return MarketDepth.from_dict(data)

    def trades(self, symbol, limit=None, date=None, after_seq=None, cursor=None):
        """
        Get live trade prints for a symbol (Pro+).

        Without ``date``, returns the most recent prints, newest first.
        With ``date``, reads one Asia/Riyadh session from the recent tape
        (about three days) in receive order and returns a ``page`` object.
        Walk a session by following ``page.next_cursor`` until
        ``page.has_more`` is false, or use :meth:`iter_trades`.

        Args:
            symbol: Stock symbol (e.g., "2222")
            limit: Optional page size (1-200). Backend default is 50.
            date: Optional session date "YYYY-MM-DD" (Asia/Riyadh).
            after_seq: Optional integer; only prints with a greater
                       ``trade_seq``. Requires ``date``. This is a filter,
                       not a pagination cursor.
            cursor: Optional opaque ``page.next_cursor`` from the previous
                    page. Requires ``date``.

        Returns:
            TradesResponse with .events, .summary, and (dated calls) .page
        """
        from .models import TradesResponse
        params = {}
        normalized_limit = self._normalize_trades_limit(limit)
        if normalized_limit is not None:
            params["limit"] = normalized_limit
        params.update(self._trades_recovery_params(date, after_seq, cursor))
        data = self._request(
            "GET",
            f"/market/trades/{symbol}/",
            params=params or None,
        )
        return TradesResponse.from_dict(data)

    def iter_trades(self, symbol, date, limit=_TRADES_LIMIT_MAX, max_pages=None):
        """
        Yield every trade print for one Asia/Riyadh session, page by page.

        Follows ``page.next_cursor`` until ``page.has_more`` is false. The
        tape can repeat a print; dedupe on (symbol, date, ``trade_seq``) and
        keep the later copy. This is the recent tape (about three days), not
        official session volume.

        Args:
            symbol: Stock symbol (e.g., "2222")
            date: Session date "YYYY-MM-DD" (Asia/Riyadh)
            limit: Page size (1-200, default 200)
            max_pages: Optional safety cap on the number of pages fetched

        Yields:
            TradeEvent objects in receive order
        """
        cursor = None
        pages = 0
        while True:
            response = self.trades(symbol, limit=limit, date=date, cursor=cursor)
            pages += 1
            for event in response.events:
                yield event
            page = response.page
            if page is None or not page.has_more or not page.next_cursor:
                return
            if max_pages is not None and pages >= max_pages:
                return
            cursor = page.next_cursor

    # -------------------------------------------------------------------------
    # Company Data
    # -------------------------------------------------------------------------

    def companies(self, search=None, market=None, limit=100, offset=0):
        """
        Discover listed companies/symbols for quote/company workflows.

        Args:
            search: Optional symbol/name search string.
            market: Optional market filter ("TASI" or "NOMU"). "NOMUC" alias
                    is accepted and normalized to "NOMU".
            limit: Page size (must be > 0, default: 100).
            offset: Pagination offset (must be >= 0, default: 0).

        Returns:
            Raw API response with keys such as results/count/total/limit/offset.
        """
        return self._request(
            "GET",
            "/companies/",
            params=self._companies_params(
                search=search,
                market=market,
                limit=limit,
                offset=offset,
            ),
        )

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

    @staticmethod
    def _clean_params(params):
        """Return params without None values (preserving False/0)."""
        cleaned = {key: value for key, value in params.items() if value is not None}
        return cleaned or None

    @staticmethod
    def _normalize_symbols(symbols):
        """Accept symbol list or comma-separated string for compare-like endpoints."""
        if isinstance(symbols, str):
            normalized = [s.strip() for s in symbols.split(",") if s.strip()]
        else:
            normalized = [str(s).strip() for s in symbols if str(s).strip()]
        if not normalized:
            raise ValueError("At least one symbol is required")
        return normalized

    def financials(
        self,
        symbol,
        type=None,
        period=None,
        statement_period=None,
        history=None,
        metrics=None,
        result=None,
        include_partial=None,
    ):
        """
        Get financial statements (income, balance sheet, cash flow). Starter+ plan.

        Args:
            symbol: Stock symbol
            type: Optional statement type filter
            period: Optional period filter. If passed with statement_period,
                    this value takes precedence.
            statement_period: Optional statement period (ignored when period set)
            history: Optional history selector (e.g. latest, 3y, 5y)
            metrics: Optional metrics set selector
            result: Optional result shape selector
            include_partial: Optional partial-period records toggle

        Returns:
            FinancialsResponse object
        """
        from .models import FinancialsResponse
        params = {
            "type": type,
            "period": period,
            "history": history,
            "metrics": metrics,
            "result": result,
            "include_partial": include_partial,
        }
        if period is None:
            params["statement_period"] = statement_period
        data = self._request(
            "GET",
            f"/financials/{symbol}/",
            params=self._clean_params(params),
        )
        return FinancialsResponse.from_dict(data)

    def ratios(self, symbol, history="latest", period="annual", metrics="core"):
        """
        Get analytics ratios for a symbol.

        Returns:
            Raw API response dict
        """
        return self._request(
            "GET",
            f"/analytics/ratios/{symbol}/",
            params=self._clean_params(
                {
                    "history": history,
                    "period": period,
                    "metrics": metrics,
                }
            ),
        )

    def compare(self, symbols, metrics="core"):
        """
        Compare analytics across multiple symbols.

        Args:
            symbols: List of symbols or comma-separated symbol string.
            metrics: Optional metrics set selector.

        Returns:
            Raw API response dict
        """
        joined_symbols = ",".join(self._normalize_symbols(symbols))
        return self._request(
            "GET",
            "/analytics/compare/",
            params=self._clean_params(
                {
                    "symbols": joined_symbols,
                    "metrics": metrics,
                }
            ),
        )

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
    # Portfolios
    # -------------------------------------------------------------------------
    #
    # Portfolio methods return the API's JSON as plain dicts. Writes are never
    # retried after a timeout or 5xx (see _request); pass an idempotency_key
    # on transactions so you can safely resend one yourself.

    @staticmethod
    def _positive_int(value, name):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a positive integer")
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a positive integer") from exc
        if normalized < 1:
            raise ValueError(f"{name} must be a positive integer")
        return normalized

    @staticmethod
    def _drop_none(fields):
        return {key: value for key, value in fields.items() if value is not None}

    def portfolios(self, workspace_id=None):
        """
        List your portfolios, most recently updated first.

        Args:
            workspace_id: Optional workspace id to filter by

        Returns:
            dict with "count" and "portfolios"
        """
        params = None
        if workspace_id is not None:
            params = {"workspace_id": self._positive_int(workspace_id, "workspace_id")}
        return self._request("GET", "/portfolios/", params=params)

    def portfolio(self, portfolio_id):
        """Get one portfolio by id."""
        pid = self._positive_int(portfolio_id, "portfolio_id")
        return self._request("GET", f"/portfolios/{pid}/")

    def create_portfolio(self, name, description=None, workspace=None, metadata=None):
        """
        Create a portfolio. Names must be unique per developer.

        Args:
            name: Portfolio name
            description: Optional description
            workspace: Optional workspace id to link
            metadata: Optional dict of your own fields

        Returns:
            dict: the created portfolio
        """
        name = str(name or "").strip()
        if not name:
            raise ValueError("name is required")
        body = self._drop_none(
            {
                "name": name,
                "description": description,
                "workspace": workspace,
                "metadata": metadata,
            }
        )
        return self._request("POST", "/portfolios/", json_body=body)

    def update_portfolio(
        self, portfolio_id, name=None, description=None, workspace=None, metadata=None
    ):
        """Rename or edit one portfolio. Only the fields you pass are changed."""
        pid = self._positive_int(portfolio_id, "portfolio_id")
        body = self._drop_none(
            {
                "name": name,
                "description": description,
                "workspace": workspace,
                "metadata": metadata,
            }
        )
        if not body:
            raise ValueError("Pass at least one field to update")
        return self._request("PATCH", f"/portfolios/{pid}/", json_body=body)

    def delete_portfolio(self, portfolio_id):
        """Delete one portfolio and its transactions. Returns None."""
        pid = self._positive_int(portfolio_id, "portfolio_id")
        return self._request("DELETE", f"/portfolios/{pid}/")

    def portfolio_transactions(self, portfolio_id):
        """
        List a portfolio's full ledger, newest first.

        Returns:
            dict with "count" and "transactions"
        """
        pid = self._positive_int(portfolio_id, "portfolio_id")
        return self._request("GET", f"/portfolios/{pid}/transactions/")

    def create_portfolio_transaction(
        self,
        portfolio_id,
        transaction_type,
        amount_sar,
        symbol=None,
        quantity=None,
        unit_price_sar=None,
        fee_sar=None,
        executed_at=None,
        notes=None,
        metadata=None,
        idempotency_key=None,
    ):
        """
        Append one transaction to a portfolio ledger.

        The ledger is append-only by ``executed_at``: an entry dated before the
        latest one is rejected.

        Args:
            portfolio_id: Portfolio id
            transaction_type: "deposit", "buy", "sell", "withdrawal",
                              "dividend", or "fee"
            amount_sar: Amount in SAR
            symbol: Stock symbol (buy, sell, dividend)
            quantity: Share quantity (buy, sell)
            unit_price_sar: Price per share in SAR (buy, sell)
            fee_sar: Optional fee in SAR
            executed_at: Optional ISO-8601 timestamp
            notes: Optional note
            metadata: Optional dict of your own fields
            idempotency_key: Optional key; resending the same key does not
                             create a second transaction

        Returns:
            dict: the created transaction
        """
        pid = self._positive_int(portfolio_id, "portfolio_id")
        transaction_type = str(transaction_type or "").strip().lower()
        if not transaction_type:
            raise ValueError("transaction_type is required")
        if amount_sar is None:
            raise ValueError("amount_sar is required")
        body = self._drop_none(
            {
                "transaction_type": transaction_type,
                "amount_sar": amount_sar,
                "symbol": symbol,
                "quantity": quantity,
                "unit_price_sar": unit_price_sar,
                "fee_sar": fee_sar,
                "executed_at": executed_at,
                "notes": notes,
                "metadata": metadata,
                "idempotency_key": idempotency_key,
            }
        )
        return self._request(
            "POST", f"/portfolios/{pid}/transactions/", json_body=body
        )

    def create_portfolio_transactions(
        self, portfolio_id, transactions, batch_idempotency_key
    ):
        """
        Append several transactions as one atomic batch.

        Args:
            portfolio_id: Portfolio id
            transactions: List of transaction dicts (same fields as
                          :meth:`create_portfolio_transaction`; each needs
                          "transaction_type" and "amount_sar")
            batch_idempotency_key: Required key for the whole batch

        Returns:
            dict: the batch result
        """
        pid = self._positive_int(portfolio_id, "portfolio_id")
        if not isinstance(transactions, list) or not transactions:
            raise ValueError("transactions must be a non-empty list")
        batch_key = str(batch_idempotency_key or "").strip()
        if not batch_key:
            raise ValueError("batch_idempotency_key is required")
        body = {"transactions": transactions, "batch_idempotency_key": batch_key}
        return self._request(
            "POST", f"/portfolios/{pid}/transactions/", json_body=body
        )

    def reverse_portfolio_transaction(
        self, portfolio_id, transaction_id, notes=None, metadata=None
    ):
        """
        Reverse a transaction. Only the portfolio's latest transaction can be
        reversed.

        Returns:
            dict: the reversal transaction
        """
        pid = self._positive_int(portfolio_id, "portfolio_id")
        tid = self._positive_int(transaction_id, "transaction_id")
        body = self._drop_none({"notes": notes, "metadata": metadata})
        return self._request(
            "POST",
            f"/portfolios/{pid}/transactions/{tid}/reverse/",
            json_body=body,
        )

    def portfolio_summary(self, portfolio_id):
        """Get cash, holdings, and P&L for one portfolio."""
        pid = self._positive_int(portfolio_id, "portfolio_id")
        return self._request("GET", f"/portfolios/{pid}/holdings/summary/")

    def portfolio_performance(self, portfolio_id, days=None):
        """
        Get a portfolio's daily equity series.

        Args:
            portfolio_id: Portfolio id
            days: Optional window in days (backend default: 30)
        """
        pid = self._positive_int(portfolio_id, "portfolio_id")
        params = None
        if days is not None:
            params = {"days": self._positive_int(days, "days")}
        return self._request("GET", f"/portfolios/{pid}/performance/", params=params)

    def set_portfolio_holdings(
        self,
        portfolio_id,
        holdings,
        scope,
        cash_policy,
        dry_run=True,
        plan_token=None,
        expected_latest_transaction_id=None,
    ):
        """
        Reconcile a portfolio to target holdings (dry-run, then apply).

        Call with ``dry_run=True`` (the default) to get a plan and its
        ``plan_token``. Then call again with ``dry_run=False`` and that
        ``plan_token`` to apply it. Applying writes ledger transactions.

        Args:
            portfolio_id: Portfolio id
            holdings: List of {"symbol", "quantity", "avg_cost_sar"} dicts
            scope: "full" or "partial"
            cash_policy: "auto_fund" (existing cash is used first, only the
                         shortfall is auto-deposited; only cash released by the
                         plan is auto-withdrawn) or "require_cash" (no automatic
                         deposits or withdrawals; blocked if cash would go
                         negative)
            dry_run: True to preview, False to apply (default: True)
            plan_token: Token from the dry run; required to apply
            expected_latest_transaction_id: Optional guard; apply fails if the
                                            ledger moved since

        Returns:
            dict with "success", "dry_run", and the plan or "result"
        """
        pid = self._positive_int(portfolio_id, "portfolio_id")
        if not isinstance(holdings, list):
            raise ValueError("holdings must be a list")
        if scope not in {"full", "partial"}:
            raise ValueError('scope must be "full" or "partial"')
        if cash_policy not in {"auto_fund", "require_cash"}:
            raise ValueError('cash_policy must be "auto_fund" or "require_cash"')
        if not dry_run and not plan_token:
            raise ValueError("plan_token from a dry run is required to apply")
        body = {
            "holdings": holdings,
            "scope": scope,
            "cash_policy": cash_policy,
            "dry_run": bool(dry_run),
        }
        if plan_token:
            body["plan_token"] = plan_token
        if expected_latest_transaction_id is not None:
            body["expected_latest_transaction_id"] = self._positive_int(
                expected_latest_transaction_id, "expected_latest_transaction_id"
            )
        return self._request(
            "POST", f"/portfolios/{pid}/holdings/set/", json_body=body
        )

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
        automatically. Per-connection subscription limits are discovered from
        the backend `connected.limits` payload when available.

        Args:
            symbols: List of stock symbols to subscribe to.
                     The SDK uses backend-provided limits
                     (`max_symbols_per_connection`, `max_symbols_per_call`)
                     from the initial `type=connected` payload when present.
            on_quote: Async callback — on_quote(data) where data contains
                      symbol, timestamp, and quote fields (price, change, etc.)
            on_error: Async callback — on_error(error_data)
            on_disconnect: Async callback — on_disconnect(reason) called when
                           the connection drops. Receives a string reason.
            on_reconnect: Async callback — on_reconnect(attempt) called before
                          a reconnect attempt (after the backoff delay).
                          Receives the attempt number.
            ping_interval: Seconds between keep-alive pings (default: 30)
            max_reconnect_attempts: Maximum reconnection attempts. 0 means
                                    unlimited reconnection (default). Set to -1
                                    to disable reconnection entirely.
            initial_reconnect_delay: Initial delay in seconds before first
                                     reconnect attempt (default: 1.0)
            max_reconnect_delay: Maximum delay in seconds between reconnect
                                 attempts (default: 60.0)

        Notes:
            - Close code 4401 indicates authentication failure and is not retried.
            - Close code 4403 indicates entitlement/plan/account access failure
              and is not retried.
            - Backend `type="error"` messages are surfaced through `on_error`
              and do not imply a disconnect by themselves.

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

                sleep_for = self._jittered_reconnect_delay(delay, max_reconnect_delay)
                logger.info(
                    "WebSocket disconnected (%s), reconnecting in %.2fs "
                    "(attempt %d, base %.2fs)...",
                    reason,
                    sleep_for,
                    attempt,
                    delay,
                )
                await asyncio.sleep(sleep_for)
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

        try:
            async with websockets.connect(url) as ws:
                msg = json.loads(await ws.recv())
                if msg.get("type") == "error":
                    raise SahmkError(
                        f"WebSocket error: {msg.get('message')}",
                        status_code=msg.get("code"),
                    )

                limits = self._extract_connected_limits(msg)
                max_symbols_per_connection = limits.get("max_symbols_per_connection")
                if (
                    max_symbols_per_connection is not None
                    and len(symbols) > max_symbols_per_connection
                ):
                    raise SahmkError(
                        "Too many symbols for this connection: "
                        f"{len(symbols)} requested, "
                        f"max {max_symbols_per_connection} allowed."
                    )

                max_symbols_per_call = (
                    limits.get("max_symbols_per_call") or _DEFAULT_WS_MAX_SYMBOLS_PER_CALL
                )

                for i in range(0, len(symbols), max_symbols_per_call):
                    batch = symbols[i : i + max_symbols_per_call]
                    await ws.send(
                        json.dumps({"action": "subscribe", "symbols": batch})
                    )
                    ack = json.loads(await ws.recv())
                    if ack.get("type") == "error":
                        raise SahmkError(
                            f"Subscribe error: {ack.get('message')}",
                            status_code=ack.get("code"),
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

                    raise ConnectionError("WebSocket connection closed by server")
                finally:
                    ping_task.cancel()
        except websockets.exceptions.ConnectionClosed as exc:
            close_frame = getattr(exc, "rcvd", None) or getattr(exc, "sent", None)
            close_code = getattr(close_frame, "code", None)
            close_reason = getattr(close_frame, "reason", None)
            if close_code is None:
                close_code = getattr(exc, "code", None)
            if close_reason is None:
                close_reason = getattr(exc, "reason", None)

            known_close_error = self._error_for_ws_close_code(close_code, close_reason)
            if known_close_error:
                raise known_close_error
            raise ConnectionError(
                "WebSocket closed "
                f"(code={close_code}, reason={close_reason or 'N/A'})"
            )

    async def stream_depth(
        self,
        symbols,
        on_depth=None,
        on_error=None,
        on_disconnect=None,
        on_reconnect=None,
        levels=None,
        ping_interval=30,
        max_reconnect_attempts=0,
        initial_reconnect_delay=1.0,
        max_reconnect_delay=60.0,
    ):
        """
        Stream real-time market depth via WebSocket.

        Uses a dedicated depth channel (`/ws/v1/market/depth/`) with full
        snapshot pushes on change. Supports automatic reconnection with
        exponential backoff and resubscribe after reconnect.

        Args:
            symbols: List of stock symbols to subscribe to.
            on_depth: Async callback — on_depth(data) for `depth_snapshot`
                      messages (book fields match REST depth payloads).
            on_error: Async callback — on_error(error_data)
            on_disconnect: Async callback — on_disconnect(reason)
            on_reconnect: Async callback — on_reconnect(attempt)
            levels: Optional book levels to request (1-20). Entitlement may
                    cap the served depth below this value.
            ping_interval: Seconds between keep-alive pings (default: 30)
            max_reconnect_attempts: Maximum reconnection attempts. 0 means
                                    unlimited reconnection (default). Set to -1
                                    to disable reconnection entirely.
            initial_reconnect_delay: Initial delay before first reconnect.
            max_reconnect_delay: Maximum delay between reconnect attempts.

        Notes:
            - Close code 4401 indicates authentication failure and is not retried.
            - Close code 4403 indicates entitlement/plan/account access failure
              and is not retried.
            - Subscribe responses may emit one or more `depth_snapshot` messages
              before the `subscribed` acknowledgement.
        """
        try:
            import websockets  # noqa: F401
        except ImportError:
            raise SahmkError(
                "websockets package required for streaming. "
                "Install it with: pip install websockets"
            )

        import asyncio

        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            raise ValueError("At least one symbol is required")

        normalized_levels = self._normalize_depth_levels(levels)
        reconnect_enabled = max_reconnect_attempts != -1
        attempt = 0
        delay = initial_reconnect_delay

        while True:
            try:
                await self._stream_depth_connection(
                    symbols=symbols,
                    on_depth=on_depth,
                    on_error=on_error,
                    levels=normalized_levels,
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

                sleep_for = self._jittered_reconnect_delay(delay, max_reconnect_delay)
                logger.info(
                    "Depth WebSocket disconnected (%s), reconnecting in %.2fs "
                    "(attempt %d, base %.2fs)...",
                    reason,
                    sleep_for,
                    attempt,
                    delay,
                )
                await asyncio.sleep(sleep_for)
                delay = min(delay * 2, max_reconnect_delay)

                if on_reconnect:
                    try:
                        await on_reconnect(attempt)
                    except Exception:
                        pass

    async def _stream_depth_connection(
        self,
        symbols,
        on_depth=None,
        on_error=None,
        levels=None,
        ping_interval=30,
    ):
        """Single depth WebSocket connection lifecycle: connect, subscribe, listen."""
        import asyncio
        import websockets

        url = f"{DEPTH_WS_URL}?api_key={self.api_key}"

        try:
            async with websockets.connect(url) as ws:
                msg = json.loads(await ws.recv())
                if msg.get("type") == "error":
                    raise SahmkError(
                        f"WebSocket error: {msg.get('message')}",
                        status_code=msg.get("code"),
                        error_code=msg.get("code")
                        if isinstance(msg.get("code"), str)
                        else None,
                    )

                limits = self._extract_connected_limits(msg)
                max_symbols_per_connection = limits.get("max_symbols_per_connection")
                if (
                    max_symbols_per_connection is not None
                    and len(symbols) > max_symbols_per_connection
                ):
                    raise SahmkError(
                        "Too many symbols for this connection: "
                        f"{len(symbols)} requested, "
                        f"max {max_symbols_per_connection} allowed."
                    )

                max_symbols_per_call = (
                    limits.get("max_symbols_per_call") or _DEFAULT_WS_MAX_SYMBOLS_PER_CALL
                )

                for i in range(0, len(symbols), max_symbols_per_call):
                    batch = symbols[i : i + max_symbols_per_call]
                    payload = {"action": "subscribe", "symbols": batch}
                    if levels is not None:
                        payload["levels"] = levels
                    await ws.send(json.dumps(payload))
                    await self._await_depth_subscribe_ack(
                        ws,
                        on_depth=on_depth,
                        on_error=on_error,
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

                        if msg_type == "depth_snapshot" and on_depth:
                            await on_depth(data)
                        elif msg_type == "error":
                            if on_error:
                                await on_error(data)
                            else:
                                logger.warning(
                                    "Depth WebSocket error (unhandled): %s",
                                    data.get("message", data),
                                )

                    raise ConnectionError("WebSocket connection closed by server")
                finally:
                    ping_task.cancel()
        except websockets.exceptions.ConnectionClosed as exc:
            close_frame = getattr(exc, "rcvd", None) or getattr(exc, "sent", None)
            close_code = getattr(close_frame, "code", None)
            close_reason = getattr(close_frame, "reason", None)
            if close_code is None:
                close_code = getattr(exc, "code", None)
            if close_reason is None:
                close_reason = getattr(exc, "reason", None)

            known_close_error = self._error_for_ws_close_code(close_code, close_reason)
            if known_close_error:
                raise known_close_error
            raise ConnectionError(
                "WebSocket closed "
                f"(code={close_code}, reason={close_reason or 'N/A'})"
            )

    async def _await_depth_subscribe_ack(self, ws, on_depth=None, on_error=None):
        """Drain post-subscribe messages until subscribed/error acknowledgement."""
        while True:
            data = json.loads(await ws.recv())
            msg_type = data.get("type")

            if msg_type == "depth_snapshot":
                if on_depth:
                    await on_depth(data)
                continue
            if msg_type == "subscribed":
                return data
            if msg_type == "error":
                if on_error:
                    await on_error(data)
                raise SahmkError(
                    f"Subscribe error: {data.get('message')}",
                    status_code=data.get("code")
                    if isinstance(data.get("code"), int)
                    else None,
                    error_code=data.get("code")
                    if isinstance(data.get("code"), str)
                    else None,
                )
            if msg_type in {"pong", "connected", "unsubscribed"}:
                continue
            # Unknown control traffic — keep waiting for subscribed/error.
            logger.debug("Ignoring depth subscribe interim message: %s", msg_type)

    @staticmethod
    def _normalize_depth_levels(levels):
        """Validate optional depth levels request (1-20)."""
        if levels is None:
            return None
        try:
            normalized = int(levels)
        except (TypeError, ValueError) as exc:
            raise ValueError("levels must be an integer between 1 and 20") from exc
        if normalized < _DEPTH_LEVELS_MIN or normalized > _DEPTH_LEVELS_MAX:
            raise ValueError(
                f"levels must be between {_DEPTH_LEVELS_MIN} and {_DEPTH_LEVELS_MAX}"
            )
        return normalized

    async def stream_trades(
        self,
        symbols,
        on_trade=None,
        on_snapshot=None,
        on_error=None,
        on_disconnect=None,
        on_reconnect=None,
        ping_interval=30,
        max_reconnect_attempts=0,
        initial_reconnect_delay=1.0,
        max_reconnect_delay=60.0,
    ):
        """
        Stream real-time trade prints via WebSocket (Pro+).

        Uses a dedicated trades channel (`/ws/v1/market/trades/`). After
        subscribe, the server typically acks with `subscribed`, then may emit
        a `trades_snapshot` per symbol before live `trade` events.

        Args:
            symbols: List of stock symbols to subscribe to.
            on_trade: Async callback — on_trade(data) for live `trade` messages.
            on_snapshot: Async callback — on_snapshot(data) for `trades_snapshot`.
            on_error: Async callback — on_error(error_data)
            on_disconnect: Async callback — on_disconnect(reason)
            on_reconnect: Async callback — on_reconnect(attempt)
            ping_interval: Seconds between keep-alive pings (default: 30)
            max_reconnect_attempts: Maximum reconnection attempts. 0 means
                                    unlimited reconnection (default). Set to -1
                                    to disable reconnection entirely.
            initial_reconnect_delay: Initial delay before first reconnect.
            max_reconnect_delay: Maximum delay between reconnect attempts.

        Notes:
            - Close code 4401 indicates authentication failure and is not retried.
            - Close code 4403 indicates entitlement/plan/account access failure
              and is not retried.
            - Snapshots may arrive before or after the `subscribed` acknowledgement;
              both are forwarded to `on_snapshot` when provided.
        """
        try:
            import websockets  # noqa: F401
        except ImportError:
            raise SahmkError(
                "websockets package required for streaming. "
                "Install it with: pip install websockets"
            )

        import asyncio

        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            raise ValueError("At least one symbol is required")

        reconnect_enabled = max_reconnect_attempts != -1
        attempt = 0
        delay = initial_reconnect_delay

        while True:
            try:
                await self._stream_trades_connection(
                    symbols=symbols,
                    on_trade=on_trade,
                    on_snapshot=on_snapshot,
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

                sleep_for = self._jittered_reconnect_delay(delay, max_reconnect_delay)
                logger.info(
                    "Trades WebSocket disconnected (%s), reconnecting in %.2fs "
                    "(attempt %d, base %.2fs)...",
                    reason,
                    sleep_for,
                    attempt,
                    delay,
                )
                await asyncio.sleep(sleep_for)
                delay = min(delay * 2, max_reconnect_delay)

                if on_reconnect:
                    try:
                        await on_reconnect(attempt)
                    except Exception:
                        pass

    async def _stream_trades_connection(
        self,
        symbols,
        on_trade=None,
        on_snapshot=None,
        on_error=None,
        ping_interval=30,
    ):
        """Single trades WebSocket connection lifecycle: connect, subscribe, listen."""
        import asyncio
        import websockets

        url = f"{TRADES_WS_URL}?api_key={self.api_key}"

        try:
            async with websockets.connect(url) as ws:
                msg = json.loads(await ws.recv())
                if msg.get("type") == "error":
                    raise SahmkError(
                        f"WebSocket error: {msg.get('message')}",
                        status_code=msg.get("code"),
                        error_code=msg.get("code")
                        if isinstance(msg.get("code"), str)
                        else None,
                    )

                limits = self._extract_connected_limits(msg)
                max_symbols_per_connection = limits.get("max_symbols_per_connection")
                if (
                    max_symbols_per_connection is not None
                    and len(symbols) > max_symbols_per_connection
                ):
                    raise SahmkError(
                        "Too many symbols for this connection: "
                        f"{len(symbols)} requested, "
                        f"max {max_symbols_per_connection} allowed."
                    )

                max_symbols_per_call = (
                    limits.get("max_symbols_per_call") or _DEFAULT_WS_MAX_SYMBOLS_PER_CALL
                )

                for i in range(0, len(symbols), max_symbols_per_call):
                    batch = symbols[i : i + max_symbols_per_call]
                    await ws.send(
                        json.dumps({"action": "subscribe", "symbols": batch})
                    )
                    await self._await_trades_subscribe_ack(
                        ws,
                        on_trade=on_trade,
                        on_snapshot=on_snapshot,
                        on_error=on_error,
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

                        if msg_type == "trade" and on_trade:
                            await on_trade(data)
                        elif msg_type == "trades_snapshot" and on_snapshot:
                            await on_snapshot(data)
                        elif msg_type == "error":
                            if on_error:
                                await on_error(data)
                            else:
                                logger.warning(
                                    "Trades WebSocket error (unhandled): %s",
                                    data.get("message", data),
                                )

                    raise ConnectionError("WebSocket connection closed by server")
                finally:
                    ping_task.cancel()
        except websockets.exceptions.ConnectionClosed as exc:
            close_frame = getattr(exc, "rcvd", None) or getattr(exc, "sent", None)
            close_code = getattr(close_frame, "code", None)
            close_reason = getattr(close_frame, "reason", None)
            if close_code is None:
                close_code = getattr(exc, "code", None)
            if close_reason is None:
                close_reason = getattr(exc, "reason", None)

            known_close_error = self._error_for_ws_close_code(close_code, close_reason)
            if known_close_error:
                raise known_close_error
            raise ConnectionError(
                "WebSocket closed "
                f"(code={close_code}, reason={close_reason or 'N/A'})"
            )

    async def _await_trades_subscribe_ack(
        self,
        ws,
        on_trade=None,
        on_snapshot=None,
        on_error=None,
    ):
        """Drain post-subscribe messages until subscribed/error acknowledgement."""
        while True:
            data = json.loads(await ws.recv())
            msg_type = data.get("type")

            if msg_type == "trades_snapshot":
                if on_snapshot:
                    await on_snapshot(data)
                continue
            if msg_type == "trade":
                if on_trade:
                    await on_trade(data)
                continue
            if msg_type == "subscribed":
                return data
            if msg_type == "error":
                if on_error:
                    await on_error(data)
                raise SahmkError(
                    f"Subscribe error: {data.get('message')}",
                    status_code=data.get("code")
                    if isinstance(data.get("code"), int)
                    else None,
                    error_code=data.get("code")
                    if isinstance(data.get("code"), str)
                    else None,
                )
            if msg_type in {"pong", "connected", "unsubscribed"}:
                continue
            logger.debug("Ignoring trades subscribe interim message: %s", msg_type)

    @staticmethod
    def _normalize_trades_limit(limit):
        """Validate optional trades limit request (1-200)."""
        if limit is None:
            return None
        try:
            normalized = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be an integer between 1 and 200") from exc
        if normalized < _TRADES_LIMIT_MIN or normalized > _TRADES_LIMIT_MAX:
            raise ValueError(
                f"limit must be between {_TRADES_LIMIT_MIN} and {_TRADES_LIMIT_MAX}"
            )
        return normalized

    @staticmethod
    def _trades_recovery_params(date=None, after_seq=None, cursor=None):
        """Validate the dated trades recovery params (date/after_seq/cursor)."""
        params = {}
        if date is not None:
            date = str(date).strip()
            if not _TRADES_DATE_RE.match(date):
                raise ValueError("date must be YYYY-MM-DD (Asia/Riyadh)")
            params["date"] = date
        if after_seq is not None:
            if isinstance(after_seq, bool):
                raise ValueError("after_seq must be a non-negative integer")
            try:
                normalized_seq = int(after_seq)
            except (TypeError, ValueError) as exc:
                raise ValueError("after_seq must be a non-negative integer") from exc
            if normalized_seq < 0:
                raise ValueError("after_seq must be a non-negative integer")
            params["after_seq"] = normalized_seq
        if cursor is not None:
            cursor = str(cursor).strip()
            if cursor:
                params["cursor"] = cursor
        if ("after_seq" in params or "cursor" in params) and "date" not in params:
            raise ValueError("date (YYYY-MM-DD, Asia/Riyadh) is required with after_seq or cursor")
        return params

    @staticmethod
    def _jittered_reconnect_delay(delay, max_reconnect_delay):
        """Return exponential backoff delay with jitter for reconnect attempts."""
        delay = max(0.0, float(delay))
        jittered = random.uniform(delay * 0.8, delay * 1.2)
        capped = min(jittered, float(max_reconnect_delay))
        return max(0.0, capped)

    @staticmethod
    def _coerce_positive_int(value):
        """Best-effort conversion of numeric limits to positive integers."""
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        if normalized <= 0:
            return None
        return normalized

    @classmethod
    def _extract_connected_limits(cls, message):
        """Extract and normalize `connected.limits` payload from backend."""
        if not isinstance(message, dict):
            return {}
        if message.get("type") != "connected":
            return {}
        limits = message.get("limits")
        if not isinstance(limits, dict):
            return {}
        normalized = dict(limits)
        normalized["max_symbols_per_connection"] = cls._coerce_positive_int(
            limits.get("max_symbols_per_connection")
        )
        normalized["max_symbols_per_call"] = cls._coerce_positive_int(
            limits.get("max_symbols_per_call")
        )
        return normalized

    @staticmethod
    def _error_for_ws_close_code(code, reason):
        """Map backend close codes to stable, non-retryable SDK errors."""
        if code == _WS_AUTH_CLOSE_CODE:
            return SahmkError(
                "WebSocket authentication failed (close code 4401).",
                status_code=code,
                error_code="WS_AUTH_FAILED",
            )
        if code == _WS_ENTITLEMENT_CLOSE_CODE:
            return SahmkError(
                "WebSocket access denied (close code 4403). "
                "Check plan, entitlement, and account verification status.",
                status_code=code,
                error_code="WS_ACCESS_DENIED",
            )
        return None
