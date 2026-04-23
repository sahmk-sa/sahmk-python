"""Integration tests for the SAHMK API client.

These tests make real API calls using the provided API key.
They are skipped unless SAHMK_API_KEY is set in the environment.
"""

import os
import asyncio
import pytest
from datetime import datetime, timedelta

from sahmk import SahmkClient
from sahmk.client import SahmkError


# Skip all tests if no API key is available
pytestmark = pytest.mark.skipif(
    not os.environ.get("SAHMK_API_KEY"),
    reason="SAHMK_API_KEY environment variable not set"
)


@pytest.fixture
def live_client():
    """Create a client using the real API key."""
    api_key = os.environ.get("SAHMK_API_KEY")
    return SahmkClient(api_key=api_key, timeout=60)


class TestLiveQuoteEndpoint:
    """Live tests for the quote endpoint."""

    def test_get_aramco_quote(self, live_client):
        """Test getting Aramco (2222) quote - the most liquid stock."""
        result = live_client.quote("2222")
        
        # Verify structure
        assert "symbol" in result
        assert result["symbol"] == "2222"
        assert "price" in result
        assert isinstance(result["price"], (int, float))
        assert "volume" in result
        assert "change" in result
        assert "name" in result or "name_en" in result
        
        print(f"\nAramco Quote: {result['price']} SAR, Change: {result.get('change', 'N/A')}")

    def test_get_rajhi_quote(self, live_client):
        """Test getting Al Rajhi (1120) quote."""
        result = live_client.quote("1120")
        
        assert result["symbol"] == "1120"
        assert "price" in result
        print(f"\nAl Rajhi Quote: {result['price']} SAR")

    def test_invalid_symbol(self, live_client):
        """Test getting quote for invalid symbol."""
        with pytest.raises(SahmkError) as exc_info:
            live_client.quote("INVALID")
        
        # Should get a 404 or similar error
        assert exc_info.value.status_code is not None
        print(f"\nExpected error for invalid symbol: {exc_info.value}")


class TestLiveBatchQuotes:
    """Live tests for batch quotes endpoint."""

    def test_get_multiple_quotes(self, live_client):
        """Test getting multiple quotes at once."""
        # Test with major Saudi stocks
        symbols = ["2222", "1120", "2010"]  # Aramco, Rajhi, SABIC
        
        result = live_client.quotes(symbols)
        
        assert "quotes" in result
        assert "count" in result
        assert result["count"] == len(symbols)
        assert len(result["quotes"]) == len(symbols)
        
        # Check each symbol is present
        returned_symbols = [q["symbol"] for q in result["quotes"]]
        for sym in symbols:
            assert sym in returned_symbols
        
        print(f"\nBatch quotes retrieved: {result['count']} symbols")
        for q in result["quotes"]:
            print(f"  {q['symbol']}: {q.get('price', 'N/A')} SAR")

    def test_batch_quotes_single_symbol(self, live_client):
        """Test batch quotes with single symbol."""
        result = live_client.quotes(["2222"])
        
        assert result["count"] == 1
        assert len(result["quotes"]) == 1
        assert result["quotes"][0]["symbol"] == "2222"


class TestLiveHistorical:
    """Live tests for historical data endpoint."""

    def test_historical_last_7_days(self, live_client):
        """Test getting 7 days of historical data."""
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        result = live_client.historical(
            "2222",
            from_date=from_date,
            to_date=to_date,
            interval="1d"
        )
        
        assert result["symbol"] == "2222"
        assert "data" in result
        assert "interval" in result
        assert result["interval"] == "1d"
        
        # Should have data points
        assert len(result["data"]) > 0
        
        # Check data structure
        first_point = result["data"][0]
        assert "date" in first_point
        assert "open" in first_point
        assert "high" in first_point
        assert "low" in first_point
        assert "close" in first_point
        assert "volume" in first_point
        
        print(f"\nHistorical data: {len(result['data'])} days retrieved")
        print(f"  From: {result.get('from', 'N/A')} To: {result.get('to', 'N/A')}")

    def test_historical_default_range(self, live_client):
        """Test historical with default date range."""
        result = live_client.historical("2222")
        
        assert "data" in result
        assert len(result["data"]) > 0
        print(f"\nDefault historical: {len(result['data'])} data points")


class TestLiveMarketData:
    """Live tests for market data endpoints."""

    def test_market_summary(self, live_client):
        """Test getting market summary."""
        result = live_client.market_summary()
        
        assert "index_value" in result
        assert "index_change" in result or "index_change_percent" in result
        assert "total_volume" in result
        
        print(f"\nMarket Summary:")
        print(f"  Index: {result.get('index_value', 'N/A')}")
        print(f"  Change: {result.get('change', 'N/A')} ({result.get('change_percent', 'N/A')}%)")
        print(f"  Volume: {result.get('volume', 'N/A')}")

    def test_gainers(self, live_client):
        """Test getting top gainers."""
        result = live_client.gainers(limit=5)
        
        assert "gainers" in result
        assert len(result["gainers"]) <= 5
        
        if result["gainers"]:
            first = result["gainers"][0]
            assert "symbol" in first
            assert "change_percent" in first
            assert first["change_percent"] > 0
        
        print(f"\nTop Gainers ({result.get('count', 0)}):")
        for g in result["gainers"][:3]:
            print(f"  {g['symbol']}: +{g.get('change_percent', 'N/A')}%")

    def test_losers(self, live_client):
        """Test getting top losers."""
        result = live_client.losers(limit=5)
        
        assert "losers" in result
        assert len(result["losers"]) <= 5
        
        if result["losers"]:
            first = result["losers"][0]
            assert "symbol" in first
            assert "change_percent" in first
            assert first["change_percent"] < 0
        
        print(f"\nTop Losers ({result.get('count', 0)}):")
        for l in result["losers"][:3]:
            print(f"  {l['symbol']}: {l.get('change_percent', 'N/A')}%")

    def test_volume_leaders(self, live_client):
        """Test getting volume leaders."""
        result = live_client.volume_leaders(limit=5)
        
        assert "stocks" in result
        assert len(result["stocks"]) <= 5
        
        if result["stocks"]:
            assert "volume" in result["stocks"][0]
        
        print(f"\nVolume Leaders ({result.get('count', 0)}):")
        for s in result["stocks"][:3]:
            print(f"  {s['symbol']}: {s.get('volume', 'N/A')} shares")

    def test_value_leaders(self, live_client):
        """Test getting value leaders."""
        result = live_client.value_leaders(limit=5)
        
        assert "stocks" in result
        assert len(result["stocks"]) <= 5
        
        if result["stocks"]:
            assert "value" in result["stocks"][0]
        
        print(f"\nValue Leaders ({result.get('count', 0)}):")
        for s in result["stocks"][:3]:
            print(f"  {s['symbol']}: {s.get('value', 'N/A')} SAR")

    def test_sectors(self, live_client):
        """Test getting sector performance."""
        result = live_client.sectors()
        
        assert "sectors" in result
        assert len(result["sectors"]) > 0
        
        first_sector = result["sectors"][0]
        assert "name" in first_sector or "name_en" in first_sector
        assert "change_percent" in first_sector
        
        print(f"\nSectors ({result.get('count', 0)}):")
        for s in result["sectors"][:5]:
            name = s.get('name_en') or s.get('name', 'N/A')
            print(f"  {name}: {s.get('change_percent', 'N/A')}%")


class TestLiveCompanyData:
    """Live tests for company data endpoints."""

    def test_companies_directory(self, live_client):
        """Test company directory endpoint for symbol discovery."""
        result = live_client.companies(search="aram", limit=5, offset=0)

        assert "results" in result
        assert "count" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result
        assert isinstance(result["results"], list)
        assert result["limit"] == 5
        assert result["offset"] == 0

        print(
            f"\nCompanies directory: {result.get('count', 0)} returned, "
            f"{result.get('total', 0)} total"
        )

    def test_company_info(self, live_client):
        """Test getting company information."""
        result = live_client.company("2222")
        
        assert "symbol" in result
        assert result["symbol"] == "2222"
        assert "name" in result or "name_en" in result
        
        print(f"\nCompany Info for 2222:")
        print(f"  Name: {result.get('name_en') or result.get('name', 'N/A')}")
        if "market_cap" in result:
            print(f"  Market Cap: {result['market_cap']:,} SAR")

    def test_financials(self, live_client):
        """Test getting financial statements."""
        try:
            result = live_client.financials("2222")
            
            assert "symbol" in result
            assert "income_statements" in result or "balance_sheets" in result or "cash_flows" in result
            
            print(f"\nFinancials for 2222 retrieved")
            if "income_statement" in result:
                print(f"  Has income statement data")
        except SahmkError as e:
            # May require higher plan
            print(f"\nFinancials endpoint requires upgrade: {e}")
            pytest.skip(f"Financials requires paid plan: {e}")

    def test_dividends(self, live_client):
        """Test getting dividend history."""
        try:
            result = live_client.dividends("2222")
            
            assert "symbol" in result
            assert "history" in result
            
            print(f"\nDividends for 2222:")
            print(f"  Yield: {result.get('dividend_yield', 'N/A')}%")
            print(f"  History entries: {len(result.get('history', []))}")
        except SahmkError as e:
            print(f"\nDividends endpoint requires upgrade: {e}")
            pytest.skip(f"Dividends requires paid plan: {e}")


class TestLiveEvents:
    """Live tests for events endpoint."""

    def test_events_basic(self, live_client):
        """Test getting recent events."""
        try:
            result = live_client.events(limit=10)
            
            assert "events" in result
            assert len(result["events"]) <= 10
            
            print(f"\nRecent Events ({result.get('count', 0)}):")
            for e in result["events"][:3]:
                print(f"  {e.get('date', 'N/A')}: {e.get('title', 'N/A')}")
        except SahmkError as e:
            print(f"\nEvents endpoint requires upgrade: {e}")
            pytest.skip(f"Events requires Pro plan: {e}")

    def test_events_by_symbol(self, live_client):
        """Test getting events for specific symbol."""
        try:
            result = live_client.events(symbol="2222", limit=5)
            
            assert "events" in result
            
            # All events should be for the requested symbol
            for event in result["events"]:
                assert event.get("symbol") == "2222"
            
            print(f"\nEvents for 2222: {result.get('count', 0)} found")
        except SahmkError as e:
            pytest.skip(f"Events requires Pro plan: {e}")


class TestLiveWebSocket:
    """Live tests for WebSocket streaming (requires Pro+ plan)."""

    @pytest.mark.asyncio
    async def test_websocket_stream_aramco(self, live_client):
        """Test streaming Aramco quotes via WebSocket."""
        try:
            quotes_received = []
            
            async def on_quote(data):
                quotes_received.append(data)
                print(f"\nWebSocket quote: {data.get('symbol')} @ {data.get('data', {}).get('price')}")
                # Stop after receiving 2 quotes
                if len(quotes_received) >= 2:
                    raise asyncio.CancelledError("Test complete")
            
            try:
                await asyncio.wait_for(
                    live_client.stream(["2222"], on_quote=on_quote),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                pass  # Expected
            except asyncio.CancelledError:
                pass  # We raised this to stop
            
            # We may or may not get quotes depending on market hours
            print(f"\nWebSocket test: {len(quotes_received)} quotes received")
            
        except SahmkError as e:
            if "plan" in str(e).lower() or "upgrade" in str(e).lower():
                pytest.skip(f"WebSocket requires Pro plan: {e}")
            raise

    @pytest.mark.asyncio  
    async def test_websocket_multiple_symbols(self, live_client):
        """Test streaming multiple symbols."""
        try:
            quotes_received = []
            
            async def on_quote(data):
                quotes_received.append(data.get('symbol'))
                if len(quotes_received) >= 3:
                    raise asyncio.CancelledError("Test complete")
            
            try:
                await asyncio.wait_for(
                    live_client.stream(["2222", "1120"], on_quote=on_quote),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                pass
            
            print(f"\nWebSocket multi-symbol: {len(quotes_received)} quotes from {set(quotes_received)}")
            
        except SahmkError as e:
            if "plan" in str(e).lower() or "upgrade" in str(e).lower():
                pytest.skip(f"WebSocket requires Pro plan: {e}")
            raise


class TestErrorHandling:
    """Tests for error handling with live API."""

    def test_invalid_api_key(self):
        """Test that invalid API key raises appropriate error."""
        client = SahmkClient(api_key="invalid_key_12345")
        
        with pytest.raises(SahmkError) as exc_info:
            client.quote("2222")
        
        assert exc_info.value.status_code in [401, 403]
        print(f"\nInvalid key correctly rejected: {exc_info.value}")

    def test_rate_limit_behavior(self, live_client):
        """Test that rapid requests don't crash (may hit rate limit)."""
        # Make several requests quickly
        results = []
        errors = []
        
        for i in range(5):
            try:
                result = live_client.quote("2222")
                results.append(result)
            except SahmkError as e:
                errors.append(e)
                if e.status_code == 429:
                    print(f"\nRate limit hit after {i+1} requests (expected)")
                    break
        
        print(f"\nRapid requests: {len(results)} success, {len(errors)} errors")
