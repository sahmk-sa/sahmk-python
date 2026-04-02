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
    """Create a SahmkClient with mock URL for testing. Retries disabled for speed."""
    return SahmkClient(api_key=api_key, base_url=mock_base_url, retries=0)


@pytest.fixture
def sample_quote_response():
    """Sample quote API response (matches live API shape)."""
    return {
        "symbol": "2222",
        "name": "أرامكو السعودية",
        "name_en": "Saudi Arabian Oil Co",
        "price": 32.45,
        "change": 0.35,
        "change_percent": 1.09,
        "open": 32.10,
        "high": 32.60,
        "low": 32.05,
        "previous_close": 32.10,
        "volume": 15000000,
        "value": 487500000.0,
        "bid": 32.40,
        "ask": 32.50,
        "liquidity": {
            "inflow_value": 300000000.0,
            "inflow_volume": 9200000,
            "inflow_trades": 8500,
            "outflow_value": 187500000.0,
            "outflow_volume": 5800000,
            "outflow_trades": 4200,
            "net_value": 112500000.0,
        },
        "updated_at": "2026-02-10T12:19:22+00:00",
        "is_delayed": False,
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
    """Sample market summary API response (matches live API shape)."""
    return {
        "timestamp": "2026-01-28T12:20:00+00:00",
        "index_value": 11950.35,
        "index_change": 125.40,
        "index_change_percent": 1.06,
        "total_volume": 350000000,
        "advancing": 142,
        "declining": 68,
        "unchanged": 15,
        "market_mood": "bullish",
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
    """Sample company info API response (matches live API shape)."""
    return {
        "symbol": "2222",
        "name": "أرامكو السعودية",
        "name_en": "Saudi Arabian Oil Co",
        "current_price": 25.64,
        "sector": "Energy",
        "industry": "Oil & Gas",
        "description": "Saudi Aramco is the world's largest oil producer...",
        "website": "https://www.aramco.com",
        "country": "Saudi Arabia",
        "currency": "SAR",
        "fundamentals": {
            "market_cap": 6258120000000,
            "pe_ratio": 16.77,
            "forward_pe": 15.48,
            "eps": 1.54,
            "book_value": 6.16,
            "price_to_book": 4.19,
            "beta": 0.104,
            "shares_outstanding": 242000000000,
            "float_shares": 5969578000,
            "week_high": 26.10,
            "week_low": 25.40,
            "month_high": 27.20,
            "month_low": 24.80,
            "fifty_two_week_high": 27.85,
            "fifty_two_week_low": 23.04,
        },
        "technicals": {
            "rsi_14": 55.3,
            "macd_line": 0.12,
            "macd_signal": 0.08,
            "macd_histogram": 0.04,
            "fifty_day_average": 26.1,
            "technical_strength": 0.65,
            "price_direction": "bullish",
            "updated_at": "2026-01-28T10:00:00+03:00",
        },
        "valuation": {
            "fair_price": 28.50,
            "fair_price_confidence": 0.85,
            "calculated_at": "2026-01-28T10:00:00+03:00",
        },
        "analysts": {
            "target_mean": 29.5,
            "target_median": 29.0,
            "target_high": 35.0,
            "target_low": 24.0,
            "consensus": "buy",
            "consensus_score": 2.1,
            "num_analysts": 15,
        },
    }


@pytest.fixture
def sample_financials_response():
    """Sample financials API response (matches live API shape)."""
    return {
        "symbol": "2222",
        "income_statements": [
            {
                "report_date": "2025-09-30",
                "total_revenue": 418116750000.0,
                "gross_profit": 215000000000.0,
                "operating_income": 180000000000.0,
                "net_income": 105000000000.0,
            }
        ],
        "balance_sheets": [
            {
                "report_date": "2025-09-30",
                "total_assets": 2516431000000.0,
                "total_liabilities": 1026431000000.0,
                "stockholders_equity": 1490000000000.0,
                "total_debt": 356540000000.0,
            }
        ],
        "cash_flows": [
            {
                "report_date": "2025-09-30",
                "operating_cash_flow": 135375000000.0,
                "investing_cash_flow": -45000000000.0,
                "financing_cash_flow": -82337000000.0,
                "free_cash_flow": 88500000000.0,
            }
        ],
    }


@pytest.fixture
def sample_dividends_response():
    """Sample dividends API response (matches live API shape)."""
    return {
        "symbol": "2222",
        "current_price": 25.64,
        "trailing_12m_yield": 4.2,
        "trailing_12m_dividends": 1.60,
        "payments_last_year": 4,
        "upcoming": [
            {
                "value": 0.40,
                "period": "Q4",
                "eligibility_date": "2026-03-15",
                "distribution_date": "2026-04-01",
            }
        ],
        "history": [
            {
                "value": 0.40,
                "value_percent": 1.5,
                "period": "Q3",
                "fiscal_year": 2025,
                "announcement_date": "2025-09-01",
                "eligibility_date": "2025-09-15",
                "distribution_date": "2025-10-01",
            }
        ],
    }


@pytest.fixture
def sample_events_response():
    """Sample events API response (matches live API shape)."""
    return {
        "events": [
            {
                "symbol": "2222",
                "stock_name": "أرامكو السعودية",
                "event_type": "FINANCIAL_REPORT",
                "importance": "important",
                "sentiment": "positive",
                "description": "أرامكو تعلن عن ارتفاع الأرباح بنسبة 13%",
                "article_date": "2026-01-29T17:10:06+00:00",
                "created_at": "2026-01-29T17:10:12+00:00",
            }
        ],
        "count": 1,
        "available_types": [
            "FINANCIAL_REPORT", "DIVIDEND_ANNOUNCEMENT", "STOCK_SPLIT",
            "MERGER_ACQUISITION", "MANAGEMENT_CHANGE",
        ],
    }
