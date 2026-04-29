"""Unit tests for the SahmkClient class."""

import pytest
import requests
import responses
from sahmk import (
    SahmkClient,
    SahmkRateLimitError,
    SahmkInvalidIndexError,
    SahmkAmbiguousIdentifierError,
    SahmkUnknownIdentifierError,
)
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

    @responses.activate
    def test_quote_with_arabic_name_identifier(self, mock_client, sample_quote_response):
        """Test quote accepts Arabic company name identifier."""
        identifier = "أرامكو السعودية"
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/{identifier}/",
            json={
                **sample_quote_response,
                "requested_identifier": identifier,
                "resolved_symbol": "2222",
                "resolution": {
                    "input": identifier,
                    "symbol": "2222",
                    "matched_by": "name_ar",
                    "match_type": "exact",
                    "is_exact": True,
                },
            },
            status=200,
        )

        result = mock_client.quote(identifier)

        assert result["symbol"] == "2222"
        assert result.requested_identifier == identifier
        assert result.resolved_symbol == "2222"
        assert result.resolution is not None
        assert result.resolution.matched_by == "name_ar"

    @responses.activate
    def test_quote_with_english_alias_identifier(self, mock_client, sample_quote_response):
        """Test quote accepts English name/alias identifier."""
        identifier = "Aramco"
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/{identifier}/",
            json={
                **sample_quote_response,
                "requested_identifier": identifier,
                "resolved_symbol": "2222",
                "matched_by": "alias",
                "match_type": "fuzzy",
            },
            status=200,
        )

        result = mock_client.quote(identifier)

        assert result["symbol"] == "2222"
        assert result.requested_identifier == identifier
        assert result.resolved_symbol == "2222"
        assert result.resolution is not None
        assert result.resolution.matched_by == "alias"


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

        request = responses.calls[0].request
        assert (
            "identifiers=2222%2C1120" in request.url
            or "identifiers=2222,1120" in request.url
        )

    @responses.activate
    def test_quotes_url_params(self, mock_client, sample_quotes_response):
        """Test batch quotes sends identifier-capable query parameters."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json=sample_quotes_response,
            status=200,
        )

        mock_client.quotes(["2222", "1120", "2010"])
        
        request = responses.calls[0].request
        assert (
            "identifiers=2222%2C1120%2C2010" in request.url
            or "identifiers=2222,1120,2010" in request.url
        )

    @responses.activate
    def test_quotes_multiple_identifier_types(self, mock_client):
        """Test batch quotes with symbol, Arabic name, and English alias."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json={
                "quotes": [
                    {"symbol": "2222", "requested_identifier": "2222"},
                    {"symbol": "1120", "requested_identifier": "الراجحي"},
                    {
                        "symbol": "2010",
                        "requested_identifier": "SABIC",
                        "resolution": {"input": "SABIC", "matched_by": "alias"},
                    },
                ],
                "count": 3,
                "resolved": [
                    {"input": "2222", "symbol": "2222", "matched_by": "symbol"},
                    {"input": "الراجحي", "symbol": "1120", "matched_by": "name_ar"},
                    {"input": "SABIC", "symbol": "2010", "matched_by": "alias"},
                ],
            },
            status=200,
        )

        result = mock_client.quotes(["2222", "الراجحي", "SABIC"])

        request = responses.calls[0].request
        assert "identifiers=" in request.url
        assert result.count == 3
        assert len(result.resolved) == 3
        assert result.resolved[1].matched_by == "name_ar"
        assert result["quotes"][2]["symbol"] == "2010"

    @responses.activate
    def test_quotes_exposes_ambiguous_and_unknown_lists(self, mock_client):
        """Test batch response includes ambiguous and unknown identifiers."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json={
                "quotes": [{"symbol": "2222", "requested_identifier": "أرامكو"}],
                "count": 1,
                "ambiguous": [
                    {
                        "identifier": "البنك",
                        "candidates": [{"symbol": "1120"}, {"symbol": "1150"}],
                    }
                ],
                "unknown": [{"identifier": "NOT_A_STOCK"}],
            },
            status=200,
        )

        result = mock_client.quotes(["أرامكو", "البنك", "NOT_A_STOCK"])

        assert result.count == 1
        assert len(result.ambiguous) == 1
        assert len(result.unknown) == 1
        assert result.unknown[0]["identifier"] == "NOT_A_STOCK"

    @responses.activate
    def test_quotes_falls_back_to_legacy_symbols_param(self, mock_client):
        """Test legacy backend fallback from identifiers to symbols query key."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json={
                "error": {
                    "code": "VALIDATION",
                    "message": "symbols query parameter is required",
                }
            },
            status=400,
        )
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json={"quotes": [{"symbol": "2222"}], "count": 1},
            status=200,
        )

        result = mock_client.quotes(["2222"])

        assert result.count == 1
        assert len(responses.calls) == 2
        first_request = responses.calls[0].request.url
        second_request = responses.calls[1].request.url
        assert "identifiers=2222" in first_request
        assert "symbols=2222" in second_request

    @responses.activate
    def test_quotes_accepts_single_string_identifier(self, mock_client):
        """Test convenience support for passing one identifier as a string."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quotes/",
            json={"quotes": [{"symbol": "2222"}], "count": 1},
            status=200,
        )

        result = mock_client.quotes("2222")

        assert result.count == 1
        request = responses.calls[0].request.url
        assert "identifiers=2222" in request

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
    def test_companies_with_search_market_and_pagination(self, mock_client):
        """Test company directory query serialization with all parameters."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/companies/",
            json={
                "results": [{"symbol": "2222", "name_en": "Saudi Aramco"}],
                "count": 1,
                "total": 1,
                "limit": 25,
                "offset": 50,
            },
            status=200,
        )

        result = mock_client.companies(
            search="aram",
            market="tasi",
            limit=25,
            offset=50,
        )

        assert result["count"] == 1
        request = responses.calls[0].request.url
        assert "search=aram" in request
        assert "market=TASI" in request
        assert "limit=25" in request
        assert "offset=50" in request

    @responses.activate
    def test_companies_market_alias_nomuc_normalizes_to_nomu(self, mock_client):
        """Test NOMUC market alias is normalized to NOMU for company discovery."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/companies/",
            json={
                "results": [{"symbol": "9510", "name_en": "Nomu Co"}],
                "count": 1,
                "total": 1,
                "limit": 10,
                "offset": 0,
            },
            status=200,
        )

        result = mock_client.companies(market="NOMUC", limit=10, offset=0)

        assert result["count"] == 1
        request = responses.calls[0].request.url
        assert "market=NOMU" in request

    def test_companies_invalid_limit_raises(self, mock_client):
        """Test company directory rejects non-positive limits."""
        with pytest.raises(ValueError, match="limit must be greater than 0"):
            mock_client.companies(limit=0)
        with pytest.raises(ValueError, match="limit must be an integer"):
            mock_client.companies(limit="100")

    def test_companies_invalid_offset_raises(self, mock_client):
        """Test company directory rejects negative/non-integer offsets."""
        with pytest.raises(ValueError, match="offset must be greater than or equal to 0"):
            mock_client.companies(offset=-1)
        with pytest.raises(ValueError, match="offset must be an integer"):
            mock_client.companies(offset="0")

    @responses.activate
    def test_companies_surfaces_api_errors_with_status_and_code(self, mock_client):
        """Test company directory surfaces API error details clearly."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/companies/",
            json={
                "error": {
                    "code": "INVALID_PARAM",
                    "message": "unsupported filter combination",
                }
            },
            status=400,
        )

        with pytest.raises(SahmkError) as exc_info:
            mock_client.companies(search="*", market="TASI")

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "INVALID_PARAM"
        assert "unsupported filter combination" in str(exc_info.value)

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
        assert "meta" not in result

    @responses.activate
    def test_financials_backwards_compat_no_kwargs(self, mock_client, sample_financials_response):
        """Test financials(symbol) keeps legacy behavior without query params."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/financials/2222/",
            json=sample_financials_response,
            status=200,
        )

        result = mock_client.financials("2222")

        assert "income_statements" in result
        request_url = responses.calls[0].request.url
        assert request_url.endswith("/financials/2222/")
        assert "meta" not in result

    @responses.activate
    def test_financials_kwargs_serialization_and_period_precedence(self, mock_client):
        """Test financials query params include new kwargs and period precedence."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/financials/1120/",
            json={"symbol": "1120", "income_statements": [], "balance_sheets": [], "cash_flows": []},
            status=200,
        )

        mock_client.financials(
            "1120",
            type="income_statement",
            period="quarterly",
            statement_period="annual",
            history="3y",
            metrics="core",
            result="latest",
            include_quality=True,
            include_partial=False,
        )

        request_url = responses.calls[0].request.url
        assert "type=income_statement" in request_url
        assert "period=quarterly" in request_url
        assert "statement_period=annual" not in request_url
        assert "history=3y" in request_url
        assert "metrics=core" in request_url
        assert "result=latest" in request_url
        assert "include_quality=True" in request_url
        assert "include_partial=False" in request_url

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


class TestAnalyticsEndpoints:
    """Tests for analytics ratios and compare endpoints."""

    @responses.activate
    def test_ratios_url_and_params(self, mock_client):
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/analytics/ratios/1120/",
            json={
                "symbol": "1120",
                "ratios": [],
                "meta": {"period": "annual", "metrics": "core", "warnings": []},
            },
            status=200,
        )

        result = mock_client.ratios("1120")

        assert result["symbol"] == "1120"
        request_url = responses.calls[0].request.url
        assert "history=latest" in request_url
        assert "period=annual" in request_url
        assert "metrics=core" in request_url
        assert set(result["meta"].keys()) == {"period", "metrics", "warnings"}
        assert "applied_profile" not in result["meta"]
        assert "plan" not in result["meta"]
        assert "source" not in result["meta"]

    @responses.activate
    def test_compare_url_and_params(self, mock_client):
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/analytics/compare/",
            json={
                "results": [],
                "count": 0,
                "meta": {"period": "annual", "metrics": "core", "warnings": []},
            },
            status=200,
        )

        result = mock_client.compare(["1120", "1180", "1010"])

        assert "results" in result
        request_url = responses.calls[0].request.url
        assert (
            "symbols=1120%2C1180%2C1010" in request_url
            or "symbols=1120,1180,1010" in request_url
        )
        assert "metrics=core" in request_url
        assert set(result["meta"].keys()) == {"period", "metrics", "warnings"}

    @responses.activate
    def test_compare_accepts_comma_string_symbols(self, mock_client):
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/analytics/compare/",
            json={
                "results": [],
                "count": 0,
                "meta": {"period": "annual", "metrics": "extended", "warnings": []},
            },
            status=200,
        )

        mock_client.compare("1120,1180,1010", metrics="extended")

        request_url = responses.calls[0].request.url
        assert (
            "symbols=1120%2C1180%2C1010" in request_url
            or "symbols=1120,1180,1010" in request_url
        )
        assert "metrics=extended" in request_url

    @responses.activate
    def test_compare_includes_coverage_in_response(self, mock_client):
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/analytics/compare/",
            json={
                "results": [
                    {
                        "symbol": "1120",
                        "company_name": "Al Rajhi",
                        "sector": "Banks",
                        "market_cap": 350000000000,
                        "current_price": 88.20,
                        "coverage": {"quality": "full", "missing": []},
                        "ratios": {"pe": 18.2},
                        "key_metrics": {"revenue_growth": 0.12},
                    }
                ],
                "count": 1,
                "meta": {"period": "annual", "metrics": "core", "warnings": []},
            },
            status=200,
        )

        result = mock_client.compare(["1120"])

        assert result["results"][0]["coverage"]["quality"] == "full"


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

    @responses.activate
    def test_ambiguous_identifier_error(self, mock_client):
        """Test ambiguous identifier maps to specialized exception."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/البنك/",
            json={
                "error": {
                    "code": "AMBIGUOUS_IDENTIFIER",
                    "message": "Multiple stocks match this identifier",
                    "details": {
                        "identifier": "البنك",
                        "candidates": [
                            {"symbol": "1120", "name": "الراجحي"},
                            {"symbol": "1150", "name": "الإنماء"},
                        ],
                    },
                }
            },
            status=400,
        )

        with pytest.raises(SahmkAmbiguousIdentifierError) as exc_info:
            mock_client.quote("البنك")

        assert exc_info.value.identifier == "البنك"
        assert len(exc_info.value.candidates) == 2
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "AMBIGUOUS_IDENTIFIER"

    @responses.activate
    def test_unknown_identifier_error(self, mock_client):
        """Test unknown identifier maps to specialized exception."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/NOT_A_STOCK/",
            json={
                "error": {
                    "code": "UNKNOWN_IDENTIFIER",
                    "message": "Identifier not found",
                    "details": {"identifier": "NOT_A_STOCK"},
                }
            },
            status=404,
        )

        with pytest.raises(SahmkUnknownIdentifierError) as exc_info:
            mock_client.quote("NOT_A_STOCK")

        assert exc_info.value.identifier == "NOT_A_STOCK"
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "UNKNOWN_IDENTIFIER"

    @responses.activate
    def test_invalid_symbol_maps_to_unknown_identifier_preserving_code(self, mock_client):
        """Test INVALID_SYMBOL maps to unknown identifier exception preserving code."""
        responses.add(
            responses.GET,
            f"{mock_client.base_url}/quote/XXXX/",
            json={
                "error": {
                    "code": "INVALID_SYMBOL",
                    "message": "Stock symbol not found in TASI or Nomu",
                    "details": {"identifier": "XXXX"},
                }
            },
            status=404,
        )

        with pytest.raises(SahmkUnknownIdentifierError) as exc_info:
            mock_client.quote("XXXX")

        assert exc_info.value.identifier == "XXXX"
        assert exc_info.value.error_code == "INVALID_SYMBOL"
        assert exc_info.value.status_code == 404


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
