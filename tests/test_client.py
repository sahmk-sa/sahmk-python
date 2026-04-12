"""Unit tests for the SahmkClient class."""

import json
import pytest
import requests
import responses
from sahmk import SahmkClient, SahmkRateLimitError, SahmkInvalidIndexError
from sahmk.client import SahmkError, BASE_URL, WS_URL


class TestClientInitialization:
    """Tests for client initialization."""

    def test_client_init_with_api_key(self, api_key):
        """Test client initializes with API key."""
        client = SahmkClient(api_key=api_key)
        assert client.api_key == api_key
        assert client.base_url == BASE_URL
        assert client.timeout == 30
        assert "X-API-Key" in client.session.headers
        assert client.session.headers["X-API-Key"] == api_key

    def test_client_init_with_custom_base_url(self, api_key):
        """Test client initializes with custom base URL."""
        custom_url = "https://custom.api.sahmk.sa/api/v1"
        client = SahmkClient(api_key=api_key, base_url=custom_url)
        assert client.base_url == custom_url

    def test_client_init_with_trailing_slash_url(self, api_key):
        """Test client strips trailing slash from base URL."""
        url_with_slash = "https://api.sahmk.sa/api/v1/"
        client = SahmkClient(api_key=api_key, base_url=url_with_slash)
        assert client.base_url == "https://api.sahmk.sa/api/v1"

    def test_client_init_with_custom_timeout(self, api_key):
        """Test client initializes with custom timeout."""
        client = SahmkClient(api_key=api_key, timeout=60)
        assert client.timeout == 60


class TestClientRequestMethod:
    """Tests for the internal _request method."""

    @responses.activate
    def test_request_success(self, mock_client, sample_quote_response):
        """Test successful API request."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/2222/",
            json=sample_quote_response,
            status=200,
        )

        result = mock_client._request("GET", "/quote/2222/")
        assert result == sample_quote_response
        assert len(responses.calls) == 1

    @responses.activate
    def test_request_with_params(self, mock_client, sample_historical_response):
        """Test request with query parameters."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/historical/2222/",
            json=sample_historical_response,
            status=200,
        )

        params = {"from": "2024-01-01", "to": "2024-01-10", "interval": "1d"}
        result = mock_client._request("GET", "/historical/2222/", params=params)
        
        assert result == sample_historical_response
        request = responses.calls[0].request
        assert "from=2024-01-01" in request.url
        assert "to=2024-01-10" in request.url
        assert "interval=1d" in request.url

    @responses.activate
    def test_request_rate_limit_error(self, mock_client):
        """Test handling of rate limit (429) error."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/2222/",
            json={"error": {"code": "RATE_LIMIT", "message": "Too many requests"}},
            status=429,
        )

        with pytest.raises(SahmkRateLimitError) as exc_info:
            mock_client._request("GET", "/quote/2222/")

        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "RATE_LIMIT"
        assert "Rate limit exceeded" in str(exc_info.value)
        assert isinstance(exc_info.value, SahmkError)

    @responses.activate
    def test_request_api_error_with_json(self, mock_client):
        """Test handling of API error with JSON response."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/INVALID/",
            json={"error": {"code": "SYMBOL_NOT_FOUND", "message": "Symbol not found"}},
            status=404,
        )

        with pytest.raises(SahmkError) as exc_info:
            mock_client._request("GET", "/quote/INVALID/")

        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "SYMBOL_NOT_FOUND"
        assert "Symbol not found" in str(exc_info.value)

    @responses.activate
    def test_request_invalid_index_error(self, mock_client):
        """Test 400 INVALID_INDEX maps to specialized exception."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/summary/",
            json={"error": {"code": "INVALID_INDEX", "message": "Invalid index"}},
            status=400,
        )

        with pytest.raises(SahmkInvalidIndexError) as exc_info:
            mock_client._request("GET", "/market/summary/", params={"index": "BAD"})

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "INVALID_INDEX"
        assert isinstance(exc_info.value, SahmkError)

    @responses.activate
    def test_request_api_error_without_json(self, mock_client):
        """Test handling of API error without JSON response."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/2222/",
            body="Internal Server Error",
            status=500,
        )

        with pytest.raises(SahmkError) as exc_info:
            mock_client._request("GET", "/quote/2222/")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "UNKNOWN"
        assert "API error 500" in str(exc_info.value)

    @responses.activate
    def test_request_non_json_200_response(self, mock_client):
        """Test handling of non-JSON 200 response (e.g. proxy HTML)."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/2222/",
            body="<html>Bad Gateway</html>",
            status=200,
            content_type="text/html",
        )

        with pytest.raises(SahmkError) as exc_info:
            mock_client._request("GET", "/quote/2222/")

        assert "non-json response" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 200

    def test_request_network_error(self, mock_client):
        """Test handling of network/request errors."""
        # Create a client with a URL that won't resolve
        import requests
        
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{mock_client.base_url}/quote/2222/",
                body=requests.ConnectionError("Connection refused"),
            )
            
            with pytest.raises(SahmkError) as exc_info:
                mock_client._request("GET", "/quote/2222/")
            
            assert "Request failed" in str(exc_info.value)


class TestQuoteEndpoint:
    """Tests for the quote endpoint."""

    @responses.activate
    def test_quote_success(self, mock_client, sample_quote_response):
        """Test getting a single quote."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/2222/",
            json=sample_quote_response,
            status=200,
        )

        result = mock_client.quote("2222")
        
        assert result["symbol"] == "2222"
        assert result["price"] == 32.45
        assert result["name_en"] == "Saudi Arabian Oil Co"

    @responses.activate
    def test_quote_different_symbol(self, mock_client, sample_quote_response):
        """Test getting quote for different symbol."""
        modified_response = {**sample_quote_response, "symbol": "1120", "name_en": "Al Rajhi"}
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/1120/",
            json=modified_response,
            status=200,
        )

        result = mock_client.quote("1120")
        assert result["symbol"] == "1120"


class TestQuotesEndpoint:
    """Tests for the batch quotes endpoint."""

    @responses.activate
    def test_quotes_success(self, mock_client, sample_quotes_response):
        """Test getting batch quotes."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json=sample_quotes_response,
            status=200,
        )

        result = mock_client.quotes(["2222", "1120"])
        
        assert result["count"] == 2
        assert len(result["quotes"]) == 2
        assert result["quotes"][0]["symbol"] == "2222"
        assert result["quotes"][1]["symbol"] == "1120"

    @responses.activate
    def test_quotes_url_params(self, mock_client, sample_quotes_response):
        """Test batch quotes sends correct URL parameters."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json=sample_quotes_response,
            status=200,
        )

        mock_client.quotes(["2222", "1120", "2010"])
        
        request = responses.calls[0].request
        assert "symbols=2222%2C1120%2C2010" in request.url or "symbols=2222,1120,2010" in request.url

    def test_quotes_empty_list(self, mock_client):
        """Test that empty symbol list raises ValueError."""
        with pytest.raises(ValueError, match="At least one symbol"):
            mock_client.quotes([])

    def test_quotes_too_many_symbols(self, mock_client):
        """Test that more than 50 symbols raises error."""
        too_many_symbols = [str(i) for i in range(51)]
        
        with pytest.raises(SahmkError) as exc_info:
            mock_client.quotes(too_many_symbols)
        
        assert "Maximum 50 symbols" in str(exc_info.value)

    def test_quotes_exactly_50_symbols(self, mock_client):
        """Test that exactly 50 symbols is allowed."""
        exactly_50 = [str(i) for i in range(50)]
        
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{mock_client.base_url}/quotes/",
                json={"quotes": [], "count": 0},
                status=200,
            )
            # Should not raise
            result = mock_client.quotes(exactly_50)
            assert result is not None


class TestHistoricalEndpoint:
    """Tests for the historical data endpoint."""

    @responses.activate
    def test_historical_basic(self, mock_client, sample_historical_response):
        """Test getting historical data with minimal params."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/historical/2222/",
            json=sample_historical_response,
            status=200,
        )

        result = mock_client.historical("2222")
        
        assert result["symbol"] == "2222"
        assert result["interval"] == "1d"
        assert "data" in result
        assert len(result["data"]) == 2

    @responses.activate
    def test_historical_with_all_params(self, mock_client, sample_historical_response):
        """Test getting historical data with all params."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/historical/2222/",
            json=sample_historical_response,
            status=200,
        )

        result = mock_client.historical(
            "2222",
            from_date="2024-01-01",
            to_date="2024-01-10",
            interval="1w"
        )
        
        request = responses.calls[0].request
        assert "from=2024-01-01" in request.url
        assert "to=2024-01-10" in request.url
        assert "interval=1w" in request.url


class TestMarketEndpoints:
    """Tests for market data endpoints."""

    @responses.activate
    def test_market_summary(self, mock_client, sample_market_summary_response):
        """Test getting market summary."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/summary/",
            json=sample_market_summary_response,
            status=200,
        )

        result = mock_client.market_summary()
        
        assert result["index"] == "TASI"
        assert result["is_delayed"] is True
        assert result["index_value"] == 11950.35
        assert result["index_change"] == 125.40
        assert result["market_mood"] == "bullish"

    @responses.activate
    def test_market_summary_with_index(self, mock_client, sample_market_summary_response):
        """Test market summary with explicit market index."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/summary/",
            json={**sample_market_summary_response, "index": "NOMU"},
            status=200,
        )

        result = mock_client.market_summary(index="NOMU")

        request = responses.calls[0].request
        assert "index=NOMU" in request.url
        assert result["index"] == "NOMU"

    @responses.activate
    def test_gainers_default(self, mock_client, sample_gainers_response):
        """Test getting gainers with default limit."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/gainers/",
            json=sample_gainers_response,
            status=200,
        )

        result = mock_client.gainers()
        
        assert "gainers" in result
        assert result["count"] == 2

    @responses.activate
    def test_gainers_with_limit(self, mock_client, sample_gainers_response):
        """Test getting gainers with specific limit."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/gainers/",
            json=sample_gainers_response,
            status=200,
        )

        result = mock_client.gainers(limit=5)
        
        request = responses.calls[0].request
        assert "limit=5" in request.url

    @responses.activate
    def test_gainers_with_index_alias(self, mock_client, sample_gainers_response):
        """Test gainers accepts NOMUC alias and normalizes to NOMU."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/gainers/",
            json={**sample_gainers_response, "index": "NOMU"},
            status=200,
        )

        result = mock_client.gainers(index="NOMUC")

        request = responses.calls[0].request
        assert "index=NOMU" in request.url
        assert result["index"] == "NOMU"

    @responses.activate
    def test_losers(self, mock_client, sample_losers_response):
        """Test getting losers."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/losers/",
            json=sample_losers_response,
            status=200,
        )

        result = mock_client.losers()
        
        assert "losers" in result
        assert result["losers"][0]["change_percent"] < 0

    @responses.activate
    def test_losers_with_limit(self, mock_client, sample_losers_response):
        """Test getting losers with limit."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/losers/",
            json=sample_losers_response,
            status=200,
        )

        result = mock_client.losers(limit=10)
        
        request = responses.calls[0].request
        assert "limit=10" in request.url

    @responses.activate
    def test_volume_leaders(self, mock_client, sample_volume_leaders_response):
        """Test getting volume leaders."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/volume/",
            json=sample_volume_leaders_response,
            status=200,
        )

        result = mock_client.volume_leaders()
        
        assert "stocks" in result
        assert result["stocks"][0]["volume"] > 0

    @responses.activate
    def test_value_leaders(self, mock_client, sample_value_leaders_response):
        """Test getting value leaders."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/value/",
            json=sample_value_leaders_response,
            status=200,
        )

        result = mock_client.value_leaders()
        
        assert "stocks" in result
        assert result["stocks"][0]["value"] > 0

    @responses.activate
    def test_sectors(self, mock_client, sample_sectors_response):
        """Test getting sector performance."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/market/sectors/",
            json=sample_sectors_response,
            status=200,
        )

        result = mock_client.sectors()
        
        assert "sectors" in result
        assert result["count"] == 2

    def test_market_methods_invalid_index_raises(self, mock_client):
        """Test invalid market index is rejected client-side."""
        with pytest.raises(SahmkInvalidIndexError):
            mock_client.market_summary(index="SP500")
        with pytest.raises(SahmkInvalidIndexError):
            mock_client.gainers(index=" ")


class TestCompanyEndpoints:
    """Tests for company data endpoints."""

    @responses.activate
    def test_company(self, mock_client, sample_company_response):
        """Test getting company info."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/company/2222/",
            json=sample_company_response,
            status=200,
        )

        result = mock_client.company("2222")
        
        assert result["symbol"] == "2222"
        assert result["name_en"] == "Saudi Arabian Oil Co"
        assert "fundamentals" in result

    @responses.activate
    def test_financials(self, mock_client, sample_financials_response):
        """Test getting financial statements."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/financials/2222/",
            json=sample_financials_response,
            status=200,
        )

        result = mock_client.financials("2222")
        
        assert "income_statements" in result
        assert "balance_sheets" in result
        assert result["income_statements"][0]["total_revenue"] == 418116750000.0

    @responses.activate
    def test_dividends(self, mock_client, sample_dividends_response):
        """Test getting dividend history."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/dividends/2222/",
            json=sample_dividends_response,
            status=200,
        )

        result = mock_client.dividends("2222")
        
        assert "trailing_12m_yield" in result
        assert "history" in result
        assert len(result["history"]) == 1


class TestEventsEndpoint:
    """Tests for the events endpoint."""

    @responses.activate
    def test_events_basic(self, mock_client, sample_events_response):
        """Test getting events without filters."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/events/",
            json=sample_events_response,
            status=200,
        )

        result = mock_client.events()
        
        assert "events" in result
        assert result["count"] == 1

    @responses.activate
    def test_events_with_symbol(self, mock_client, sample_events_response):
        """Test getting events filtered by symbol."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/events/",
            json=sample_events_response,
            status=200,
        )

        result = mock_client.events(symbol="2222")
        
        request = responses.calls[0].request
        assert "symbol=2222" in request.url

    @responses.activate
    def test_events_with_limit(self, mock_client, sample_events_response):
        """Test getting events with limit."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/events/",
            json=sample_events_response,
            status=200,
        )

        result = mock_client.events(limit=50)
        
        request = responses.calls[0].request
        assert "limit=50" in request.url

    @responses.activate
    def test_events_with_all_params(self, mock_client, sample_events_response):
        """Test getting events with all parameters."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/events/",
            json=sample_events_response,
            status=200,
        )

        result = mock_client.events(symbol="2222", limit=20)
        
        request = responses.calls[0].request
        assert "symbol=2222" in request.url
        assert "limit=20" in request.url


class TestSahmkError:
    """Tests for the SahmkError exception class."""

    def test_error_basic(self):
        """Test basic error creation."""
        error = SahmkError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.status_code is None
        assert error.error_code is None

    def test_error_with_status_code(self):
        """Test error with status code."""
        error = SahmkError("Not found", status_code=404)
        assert error.status_code == 404
        assert error.error_code is None

    def test_error_with_error_code(self):
        """Test error with error code."""
        error = SahmkError("Rate limited", status_code=429, error_code="RATE_LIMIT")
        assert error.status_code == 429
        assert error.error_code == "RATE_LIMIT"

    def test_error_with_response(self):
        """Test error with response object."""
        mock_response = {"data": "test"}
        error = SahmkError("Error", status_code=500, response=mock_response)
        assert error.response == mock_response


class TestSahmkInvalidIndexError:
    """Tests for the invalid-index exception class."""

    def test_invalid_index_error_defaults(self):
        error = SahmkInvalidIndexError("Invalid market index")
        assert str(error) == "Invalid market index"
        assert error.status_code == 400
        assert error.error_code == "INVALID_INDEX"


class TestWebsocketURL:
    """Tests for WebSocket URL constant."""

    def test_ws_url_constant(self):
        """Test that WS_URL is defined correctly."""
        assert WS_URL == "wss://app.sahmk.sa/ws/v1/stocks/"
        assert WS_URL.startswith("wss://")
