"""Tests for typed response models."""

import pytest
import responses
from sahmk import SahmkClient
from sahmk.models import (
    Quote,
    Liquidity,
    BatchQuote,
    BatchQuotesResponse,
    HistoricalResponse,
    OHLCV,
    MarketSummary,
    MarketMover,
    MarketMoversResponse,
    Sector,
    SectorsResponse,
    Company,
    Fundamentals,
    Technicals,
    Valuation,
    Analysts,
    FinancialsResponse,
    IncomeStatement,
    BalanceSheet,
    CashFlow,
    RatioRow,
    RatiosResponse,
    CompareRow,
    CompareResponse,
    DividendsResponse,
    DividendPayment,
    Event,
    EventsResponse,
)


@pytest.fixture
def client():
    return SahmkClient(
        api_key="shmk_test_models",
        base_url="https://mock-api.sahmk.sa/api/v1",
        retries=0,
    )


QUOTE_DATA = {
    "symbol": "2222",
    "name": "أرامكو السعودية",
    "name_en": "Saudi Arabian Oil Co",
    "price": 25.86,
    "change": 0.18,
    "change_percent": 0.7,
    "open": 25.6,
    "high": 25.86,
    "low": 25.6,
    "previous_close": 25.68,
    "volume": 9803705,
    "value": 252308343.0,
    "bid": 25.82,
    "ask": 25.86,
    "liquidity": {
        "inflow_value": 184950463.03,
        "inflow_volume": 7182468,
        "inflow_trades": 7261,
        "outflow_value": 67357881.91,
        "outflow_volume": 2621237,
        "outflow_trades": 5028,
        "net_value": 117592581.12,
    },
    "updated_at": "2026-02-10T12:19:22+00:00",
    "is_delayed": False,
}


class TestQuoteModel:
    def test_from_dict(self):
        q = Quote.from_dict(QUOTE_DATA)
        assert q.symbol == "2222"
        assert q.price == 25.86
        assert q.name_en == "Saudi Arabian Oil Co"
        assert q.volume == 9803705
        assert q.is_delayed is False

    def test_liquidity_nested(self):
        q = Quote.from_dict(QUOTE_DATA)
        assert q.liquidity is not None
        assert q.liquidity.net_value == 117592581.12
        assert q.liquidity.inflow_trades == 7261

    def test_dict_access_backwards_compat(self):
        q = Quote.from_dict(QUOTE_DATA)
        assert q["symbol"] == "2222"
        assert q["price"] == 25.86
        assert "volume" in q
        assert q.get("nonexistent", "default") == "default"

    def test_raw_attribute(self):
        q = Quote.from_dict(QUOTE_DATA)
        assert q.raw == QUOTE_DATA
        assert q.raw is QUOTE_DATA

    @responses.activate
    def test_client_returns_quote(self, client):
        responses.add(
            responses.GET,
            f"{client.base_url}/quote/2222/",
            json=QUOTE_DATA,
            status=200,
        )
        result = client.quote("2222")
        assert isinstance(result, Quote)
        assert result.symbol == "2222"
        assert result["price"] == 25.86


class TestBatchQuotesModel:
    def test_from_dict(self):
        data = {
            "quotes": [
                {"symbol": "2222", "price": 25.86, "net_liquidity": 117592581.12},
                {"symbol": "1120", "price": 88.20},
            ],
            "count": 2,
        }
        resp = BatchQuotesResponse.from_dict(data)
        assert resp.count == 2
        assert len(resp.quotes) == 2
        assert isinstance(resp.quotes[0], BatchQuote)
        assert resp.quotes[0].symbol == "2222"
        assert resp.quotes[0].net_liquidity == 117592581.12

    def test_dict_access(self):
        data = {"quotes": [{"symbol": "2222"}], "count": 1}
        resp = BatchQuotesResponse.from_dict(data)
        assert resp["count"] == 1
        assert resp["quotes"][0]["symbol"] == "2222"

    @responses.activate
    def test_client_returns_batch(self, client):
        data = {"quotes": [{"symbol": "2222", "price": 25.86}], "count": 1}
        responses.add(
            responses.GET,
            f"{client.base_url}/quotes/",
            json=data,
            status=200,
        )
        result = client.quotes(["2222"])
        assert isinstance(result, BatchQuotesResponse)
        assert result.count == 1


class TestHistoricalModel:
    def test_from_dict(self):
        data = {
            "symbol": "2222",
            "interval": "1d",
            "from": "2026-01-01",
            "to": "2026-01-28",
            "count": 1,
            "data": [
                {"date": "2026-01-28", "open": 25.3, "high": 25.68,
                 "low": 25.3, "close": 25.64, "volume": 15738067,
                 "adjusted_close": 25.64, "turnover": 402108076.72},
            ],
        }
        resp = HistoricalResponse.from_dict(data)
        assert resp.symbol == "2222"
        assert resp.interval == "1d"
        assert resp.from_date == "2026-01-01"
        assert resp.to_date == "2026-01-28"
        assert len(resp.data) == 1
        assert isinstance(resp.data[0], OHLCV)
        assert resp.data[0].close == 25.64
        assert resp.data[0].turnover == 402108076.72

    def test_dict_access(self):
        data = {"symbol": "2222", "interval": "1d", "data": [], "from": "2026-01-01"}
        resp = HistoricalResponse.from_dict(data)
        assert resp["symbol"] == "2222"
        assert resp["from"] == "2026-01-01"


class TestMarketModels:
    def test_market_summary(self):
        data = {
            "index": "TASI",
            "is_delayed": True,
            "index_value": 11458.11,
            "index_change": 76.28,
            "index_change_percent": 0.67,
            "total_volume": 279874553,
            "advancing": 117,
            "declining": 139,
            "market_mood": "bullish",
        }
        ms = MarketSummary.from_dict(data)
        assert ms.index == "TASI"
        assert ms.is_delayed is True
        assert ms.index_value == 11458.11
        assert ms.market_mood == "bullish"
        assert ms["advancing"] == 117

    def test_market_movers_from_gainers(self):
        data = {
            "index": "NOMU",
            "is_delayed": True,
            "gainers": [{"symbol": "4194", "price": 59.5, "change_percent": 8.97}],
            "count": 1,
        }
        resp = MarketMoversResponse.from_dict(data, list_key="gainers")
        assert resp.count == 1
        assert resp.index == "NOMU"
        assert resp.is_delayed is True
        assert len(resp.stocks) == 1
        assert resp.stocks[0].change_percent == 8.97

    def test_market_movers_from_losers(self):
        data = {
            "index": "TASI",
            "is_delayed": False,
            "losers": [{"symbol": "9639", "change_percent": -8.89}],
            "count": 1,
        }
        resp = MarketMoversResponse.from_dict(data, list_key="losers")
        assert resp.index == "TASI"
        assert resp.is_delayed is False
        assert resp.stocks[0].change_percent == -8.89

    def test_sectors(self):
        data = {
            "index": "TASI",
            "is_delayed": True,
            "sectors": [
                {"id": "TBNI", "name": "Banks", "change_percent": 0.45, "num_stocks": 10},
            ],
            "count": 1,
        }
        resp = SectorsResponse.from_dict(data)
        assert resp.count == 1
        assert resp.index == "TASI"
        assert resp.is_delayed is True
        assert isinstance(resp.sectors[0], Sector)
        assert resp.sectors[0].id == "TBNI"
        assert resp.sectors[0].num_stocks == 10

    @responses.activate
    def test_client_gainers(self, client):
        data = {"index": "NOMU", "is_delayed": True, "gainers": [{"symbol": "4194", "change_percent": 8.97}], "count": 1}
        responses.add(
            responses.GET,
            f"{client.base_url}/market/gainers/",
            json=data,
            status=200,
        )
        result = client.gainers(index="nomuc")
        assert isinstance(result, MarketMoversResponse)
        assert result.index == "NOMU"
        assert result.stocks[0].symbol == "4194"
        request = responses.calls[0].request
        assert "index=NOMU" in request.url

    @responses.activate
    def test_client_losers(self, client):
        data = {"losers": [{"symbol": "9639", "change_percent": -8.89}], "count": 1}
        responses.add(
            responses.GET,
            f"{client.base_url}/market/losers/",
            json=data,
            status=200,
        )
        result = client.losers()
        assert isinstance(result, MarketMoversResponse)

    @responses.activate
    def test_client_sectors(self, client):
        data = {"sectors": [{"id": "TBNI", "name": "Banks"}], "count": 1}
        responses.add(
            responses.GET,
            f"{client.base_url}/market/sectors/",
            json=data,
            status=200,
        )
        result = client.sectors()
        assert isinstance(result, SectorsResponse)


class TestCompanyModel:
    COMPANY_DATA = {
        "symbol": "2222",
        "name_en": "Saudi Arabian Oil Co",
        "current_price": 25.64,
        "sector": "Energy",
        "fundamentals": {
            "market_cap": 6258120000000,
            "pe_ratio": 16.77,
            "eps": 1.54,
            "beta": 0.104,
            "fifty_two_week_high": 27.85,
        },
        "technicals": {
            "rsi_14": 55.3,
            "price_direction": "bullish",
        },
        "valuation": {
            "fair_price": 28.50,
            "fair_price_confidence": 0.85,
        },
        "analysts": {
            "consensus": "buy",
            "num_analysts": 15,
            "target_mean": 29.5,
        },
    }

    def test_from_dict_full(self):
        c = Company.from_dict(self.COMPANY_DATA)
        assert c.symbol == "2222"
        assert c.sector == "Energy"
        assert c.fundamentals.pe_ratio == 16.77
        assert c.technicals.rsi_14 == 55.3
        assert c.valuation.fair_price == 28.50
        assert c.analysts.consensus == "buy"

    def test_from_dict_free_plan(self):
        data = {"symbol": "2222", "name_en": "Aramco", "sector": "Energy"}
        c = Company.from_dict(data)
        assert c.symbol == "2222"
        assert c.fundamentals is None
        assert c.technicals is None

    def test_dict_access(self):
        c = Company.from_dict(self.COMPANY_DATA)
        assert c["symbol"] == "2222"
        assert c["fundamentals"]["market_cap"] == 6258120000000

    @responses.activate
    def test_client_returns_company(self, client):
        responses.add(
            responses.GET,
            f"{client.base_url}/company/2222/",
            json=self.COMPANY_DATA,
            status=200,
        )
        result = client.company("2222")
        assert isinstance(result, Company)
        assert result.fundamentals.eps == 1.54


class TestFinancialsModel:
    FINANCIALS_DATA = {
        "symbol": "2222",
        "income_statements": [
            {"report_date": "2025-09-30", "total_revenue": 418116750000.0,
             "net_income": 105000000000.0},
        ],
        "balance_sheets": [
            {"report_date": "2025-09-30", "total_assets": 2516431000000.0},
        ],
        "cash_flows": [
            {"report_date": "2025-09-30", "free_cash_flow": 88500000000.0},
        ],
    }

    def test_from_dict(self):
        f = FinancialsResponse.from_dict(self.FINANCIALS_DATA)
        assert f.symbol == "2222"
        assert len(f.income_statements) == 1
        assert f.income_statements[0].total_revenue == 418116750000.0
        assert f.balance_sheets[0].total_assets == 2516431000000.0
        assert f.cash_flows[0].free_cash_flow == 88500000000.0

    @responses.activate
    def test_client_returns_financials(self, client):
        responses.add(
            responses.GET,
            f"{client.base_url}/financials/2222/",
            json=self.FINANCIALS_DATA,
            status=200,
        )
        result = client.financials("2222")
        assert isinstance(result, FinancialsResponse)


class TestDividendsModel:
    DIVIDENDS_DATA = {
        "symbol": "2222",
        "current_price": 25.64,
        "trailing_12m_yield": 4.2,
        "trailing_12m_dividends": 1.60,
        "payments_last_year": 4,
        "upcoming": [
            {"value": 0.40, "period": "Q4", "eligibility_date": "2026-03-15"},
        ],
        "history": [
            {"value": 0.40, "period": "Q3", "fiscal_year": 2025,
             "distribution_date": "2025-10-01"},
        ],
    }

    def test_from_dict(self):
        d = DividendsResponse.from_dict(self.DIVIDENDS_DATA)
        assert d.symbol == "2222"
        assert d.trailing_12m_yield == 4.2
        assert len(d.upcoming) == 1
        assert d.upcoming[0].value == 0.40
        assert len(d.history) == 1
        assert d.history[0].fiscal_year == 2025

    @responses.activate
    def test_client_returns_dividends(self, client):
        responses.add(
            responses.GET,
            f"{client.base_url}/dividends/2222/",
            json=self.DIVIDENDS_DATA,
            status=200,
        )
        result = client.dividends("2222")
        assert isinstance(result, DividendsResponse)
        assert result.trailing_12m_yield == 4.2


class TestAnalyticsModels:
    RATIOS_DATA = {
        "symbol": "1120",
        "rows": [
            {
                "report_date": "2025-12-31",
                "statement_period": "annual",
                "fiscal_year": 2025,
                "fiscal_quarter": 4,
                "ratios": {
                    "roe": 0.214,
                    "custom_sector_ratio_x": 12.5,
                },
                "key_metrics": {
                    "net_income_growth": 0.08,
                    "custom_metric_y": 1.2,
                },
            }
        ],
        "meta": {"history": "latest", "period": "annual", "metrics": "core"},
    }

    COMPARE_DATA = {
        "rows": [
            {
                "symbol": "1120",
                "company_name": "Al Rajhi Bank",
                "sector": "Banks",
                "market_cap": 350000000000,
                "current_price": 88.2,
                "coverage": {"quality": "full", "missing": []},
                "ratios": {"pe": 18.2, "pb": 3.1},
                "key_metrics": {"revenue_growth": 0.1},
            }
        ],
        "meta": {"metrics": "core"},
    }

    def test_ratios_dynamic_keys_do_not_crash_parsing(self):
        resp = RatiosResponse.from_dict(self.RATIOS_DATA)
        assert len(resp.rows) == 1
        assert isinstance(resp.rows[0], RatioRow)
        assert resp.rows[0].ratios["custom_sector_ratio_x"] == 12.5
        assert resp.rows[0].key_metrics["custom_metric_y"] == 1.2
        assert resp.meta["metrics"] == "core"

    def test_compare_includes_coverage(self):
        resp = CompareResponse.from_dict(self.COMPARE_DATA)
        assert len(resp.rows) == 1
        assert isinstance(resp.rows[0], CompareRow)
        assert resp.rows[0].coverage["quality"] == "full"
        assert resp.rows[0].ratios["pe"] == 18.2

    @responses.activate
    def test_client_returns_ratios(self, client):
        responses.add(
            responses.GET,
            f"{client.base_url}/ratios/1120/",
            json=self.RATIOS_DATA,
            status=200,
        )
        result = client.ratios("1120")
        assert isinstance(result, RatiosResponse)
        assert result.rows[0].report_date == "2025-12-31"

    @responses.activate
    def test_client_returns_compare(self, client):
        responses.add(
            responses.GET,
            f"{client.base_url}/compare/",
            json=self.COMPARE_DATA,
            status=200,
        )
        result = client.compare(["1120", "1180"])
        assert isinstance(result, CompareResponse)
        assert result.rows[0].company_name == "Al Rajhi Bank"


class TestEventsModel:
    EVENTS_DATA = {
        "events": [
            {
                "symbol": "4190",
                "stock_name": "جرير للتسويق",
                "event_type": "FINANCIAL_REPORT",
                "importance": "important",
                "sentiment": "positive",
                "description": "شركة جرير تعلن عن نتائج مالية قياسية",
                "article_date": "2026-01-29T17:10:06+00:00",
            },
        ],
        "count": 1,
        "available_types": ["FINANCIAL_REPORT", "DIVIDEND_ANNOUNCEMENT"],
    }

    def test_from_dict(self):
        resp = EventsResponse.from_dict(self.EVENTS_DATA)
        assert resp.count == 1
        assert len(resp.events) == 1
        assert resp.events[0].event_type == "FINANCIAL_REPORT"
        assert resp.events[0].sentiment == "positive"
        assert resp.available_types == ["FINANCIAL_REPORT", "DIVIDEND_ANNOUNCEMENT"]

    @responses.activate
    def test_client_returns_events(self, client):
        responses.add(
            responses.GET,
            f"{client.base_url}/events/",
            json=self.EVENTS_DATA,
            status=200,
        )
        result = client.events()
        assert isinstance(result, EventsResponse)
        assert result.events[0].symbol == "4190"


class TestDictAccessMixin:
    """Test the dict-access mixin used by all models."""

    def test_getitem(self):
        q = Quote.from_dict({"symbol": "2222", "price": 30.0})
        assert q["symbol"] == "2222"

    def test_contains(self):
        q = Quote.from_dict({"symbol": "2222"})
        assert "symbol" in q
        assert "nonexistent" not in q

    def test_get_with_default(self):
        q = Quote.from_dict({"symbol": "2222"})
        assert q.get("symbol") == "2222"
        assert q.get("missing", 42) == 42

    def test_keys_values_items(self):
        data = {"symbol": "2222", "price": 30.0}
        q = Quote.from_dict(data)
        assert set(q.keys()) == set(data.keys())
        assert list(q.values()) == list(data.values())
        assert list(q.items()) == list(data.items())

    def test_missing_key_raises_keyerror(self):
        q = Quote.from_dict({"symbol": "2222"})
        with pytest.raises(KeyError):
            _ = q["nonexistent"]

    def test_optional_fields_default_none(self):
        q = Quote.from_dict({})
        assert q.symbol is None
        assert q.price is None
        assert q.liquidity is None
