"""Pytest fixtures and configuration."""

import pytest
from sahmk import SahmkClient


@pytest.fixture
def api_key():
    """Test API key fixture."""
    return "shmk_test_1234567890abcdef"


@pytest.fixture
def client(api_key):
    """Create a SahmkClient instance for testing."""
    return SahmkClient(api_key=api_key)


@pytest.fixture
def mock_base_url():
    """Mock base URL for testing."""
    return "https://mock-api.sahmk.sa/api/v1"


@pytest.fixture
def mock_client(api_key, mock_base_url):
    """Create a SahmkClient with mock URL for testing."""
    return SahmkClient(api_key=api_key, base_url=mock_base_url)


@pytest.fixture
def sample_quote_response():
    """Sample quote API response."""
    return {
        "symbol": "2222",
        "name": "أرامكو السعودية",
        "name_en": "Saudi Aramco",
        "price": 32.45,
        "change": 0.35,
        "change_percent": 1.09,
        "volume": 15000000,
        "bid": 32.40,
        "ask": 32.50,
        "liquidity": 487500000,
        "open": 32.10,
        "high": 32.60,
        "low": 32.05,
        "previous_close": 32.10,
    }


@pytest.fixture
def sample_quotes_response():
    """Sample batch quotes API response."""
    return {
        "quotes": [
            {
                "symbol": "2222",
                "name": "أرامكو السعودية",
                "price": 32.45,
                "change": 0.35,
                "change_percent": 1.09,
            },
            {
                "symbol": "1120",
                "name": "الراجحي",
                "price": 88.20,
                "change": -0.50,
                "change_percent": -0.56,
            },
        ],
        "count": 2,
    }


@pytest.fixture
def sample_historical_response():
    """Sample historical data API response."""
    return {
        "symbol": "2222",
        "interval": "1d",
        "from": "2024-01-01",
        "to": "2024-01-10",
        "count": 10,
        "data": [
            {"date": "2024-01-01", "open": 32.0, "high": 32.5, "low": 31.9, "close": 32.4, "volume": 12000000},
            {"date": "2024-01-02", "open": 32.4, "high": 32.8, "low": 32.2, "close": 32.6, "volume": 13500000},
        ],
    }


@pytest.fixture
def sample_market_summary_response():
    """Sample market summary API response."""
    return {
        "index": "TASI",
        "index_value": 11950.35,
        "change": 125.40,
        "change_percent": 1.06,
        "volume": 350000000,
        "value": 8750000000,
        "market_mood": "bullish",
        "up_count": 142,
        "down_count": 68,
        "unchanged_count": 15,
    }


@pytest.fixture
def sample_gainers_response():
    """Sample gainers API response."""
    return {
        "gainers": [
            {"symbol": "1234", "name": "شركة اختبار", "change_percent": 9.95, "price": 45.20},
            {"symbol": "5678", "name": "Test Co", "change_percent": 8.50, "price": 22.10},
        ],
        "count": 2,
    }


@pytest.fixture
def sample_losers_response():
    """Sample losers API response."""
    return {
        "losers": [
            {"symbol": "9012", "name": "شركة خسارة", "change_percent": -9.80, "price": 15.30},
            {"symbol": "3456", "name": "Loss Co", "change_percent": -7.25, "price": 8.90},
        ],
        "count": 2,
    }


@pytest.fixture
def sample_volume_leaders_response():
    """Sample volume leaders API response."""
    return {
        "stocks": [
            {"symbol": "2222", "name": "أرامكو", "volume": 25000000, "value": 812500000},
            {"symbol": "1120", "name": "الراجحي", "volume": 18000000, "value": 1587600000},
        ],
        "count": 2,
    }


@pytest.fixture
def sample_value_leaders_response():
    """Sample value leaders API response."""
    return {
        "stocks": [
            {"symbol": "2222", "name": "أرامكو", "value": 812500000, "volume": 25000000},
            {"symbol": "2010", "name": "سابك", "value": 625000000, "volume": 5200000},
        ],
        "count": 2,
    }


@pytest.fixture
def sample_sectors_response():
    """Sample sectors API response."""
    return {
        "sectors": [
            {"name": "البنوك", "name_en": "Banks", "change_percent": 1.25, "performance": "up"},
            {"name": "البترول", "name_en": "Energy", "change_percent": 0.85, "performance": "up"},
        ],
        "count": 2,
    }


@pytest.fixture
def sample_company_response():
    """Sample company info API response."""
    return {
        "symbol": "2222",
        "name": "أرامكو السعودية",
        "name_en": "Saudi Arabian Oil Company",
        "sector": "البترول",
        "sector_en": "Energy",
        "market_cap": 7500000000000,
        "shares_outstanding": 231000000000,
        "website": "https://www.aramco.com",
        "description": "شركة النفط والغاز العملاقة",
    }


@pytest.fixture
def sample_financials_response():
    """Sample financials API response."""
    return {
        "symbol": "2222",
        "income_statement": {
            "revenue": 1500000000000,
            "net_income": 490000000000,
            "eps": 2.11,
        },
        "balance_sheet": {
            "total_assets": 2200000000000,
            "total_equity": 1540000000000,
        },
    }


@pytest.fixture
def sample_dividends_response():
    """Sample dividends API response."""
    return {
        "symbol": "2222",
        "dividend_yield": 3.85,
        "payout_ratio": 0.67,
        "history": [
            {"date": "2024-06-15", "amount": 0.3198, "type": "quarterly"},
            {"date": "2024-03-15", "amount": 0.3198, "type": "quarterly"},
        ],
    }


@pytest.fixture
def sample_events_response():
    """Sample events API response."""
    return {
        "events": [
            {
                "id": "evt_123",
                "symbol": "2222",
                "type": "earnings",
                "title": "إعلان النتائج المالية",
                "date": "2024-08-10",
                "summary": "أرامكو تعلن عن ارتفاع الأرباح",
            }
        ],
        "count": 1,
        "available_types": ["earnings", "dividend", "news", "technical"],
    }
