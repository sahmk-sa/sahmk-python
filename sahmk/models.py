"""Typed response models for the SAHMK API.

These models provide IDE autocompletion and type safety while preserving full
backwards compatibility — every model supports dict-style access via [] and
exposes the original API response as the `raw` attribute.

All fields are Optional because the API may return different fields depending
on the subscription plan and data availability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class _DictAccessMixin:
    """Enables dict-style access on dataclass instances for backwards compat.

    Delegates [] lookups and .get() to the `raw` dict so that existing code
    like ``quote["price"]`` continues to work.
    """

    raw: Dict[str, Any]

    def __getitem__(self, key):
        return self.raw[key]

    def __contains__(self, key):
        return key in self.raw

    def get(self, key, default=None):
        return self.raw.get(key, default)

    def keys(self):
        return self.raw.keys()

    def values(self):
        return self.raw.values()

    def items(self):
        return self.raw.items()


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------

@dataclass
class Liquidity(_DictAccessMixin):
    """Money-flow data embedded in a quote."""

    inflow_value: Optional[float] = None
    inflow_volume: Optional[int] = None
    inflow_trades: Optional[int] = None
    outflow_value: Optional[float] = None
    outflow_volume: Optional[int] = None
    outflow_trades: Optional[int] = None
    net_value: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Liquidity":
        return cls(
            inflow_value=data.get("inflow_value"),
            inflow_volume=data.get("inflow_volume"),
            inflow_trades=data.get("inflow_trades"),
            outflow_value=data.get("outflow_value"),
            outflow_volume=data.get("outflow_volume"),
            outflow_trades=data.get("outflow_trades"),
            net_value=data.get("net_value"),
            raw=data,
        )


@dataclass
class Quote(_DictAccessMixin):
    """A single stock quote from GET /quote/{symbol}/."""

    symbol: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[int] = None
    value: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    liquidity: Optional[Liquidity] = None
    updated_at: Optional[str] = None
    is_delayed: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Quote":
        liq_data = data.get("liquidity")
        liq = Liquidity.from_dict(liq_data) if isinstance(liq_data, dict) else None
        return cls(
            symbol=data.get("symbol"),
            name=data.get("name"),
            name_en=data.get("name_en"),
            price=data.get("price"),
            change=data.get("change"),
            change_percent=data.get("change_percent"),
            open=data.get("open"),
            high=data.get("high"),
            low=data.get("low"),
            previous_close=data.get("previous_close"),
            volume=data.get("volume"),
            value=data.get("value"),
            bid=data.get("bid"),
            ask=data.get("ask"),
            liquidity=liq,
            updated_at=data.get("updated_at"),
            is_delayed=data.get("is_delayed"),
            raw=data,
        )


@dataclass
class BatchQuote(_DictAccessMixin):
    """A quote item from the batch GET /quotes/ response."""

    symbol: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    net_liquidity: Optional[float] = None
    updated_at: Optional[str] = None
    is_delayed: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchQuote":
        return cls(
            symbol=data.get("symbol"),
            name=data.get("name"),
            name_en=data.get("name_en"),
            price=data.get("price"),
            change=data.get("change"),
            change_percent=data.get("change_percent"),
            volume=data.get("volume"),
            net_liquidity=data.get("net_liquidity"),
            updated_at=data.get("updated_at"),
            is_delayed=data.get("is_delayed"),
            raw=data,
        )


@dataclass
class BatchQuotesResponse(_DictAccessMixin):
    """Response from GET /quotes/."""

    quotes: List[BatchQuote] = field(default_factory=list)
    count: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchQuotesResponse":
        quotes = [BatchQuote.from_dict(q) for q in data.get("quotes", [])]
        return cls(quotes=quotes, count=data.get("count"), raw=data)


# ---------------------------------------------------------------------------
# Historical
# ---------------------------------------------------------------------------

@dataclass
class OHLCV(_DictAccessMixin):
    """A single OHLCV data point."""

    date: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    adjusted_close: Optional[float] = None
    turnover: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OHLCV":
        return cls(
            date=data.get("date"),
            open=data.get("open"),
            high=data.get("high"),
            low=data.get("low"),
            close=data.get("close"),
            volume=data.get("volume"),
            adjusted_close=data.get("adjusted_close"),
            turnover=data.get("turnover"),
            raw=data,
        )


@dataclass
class HistoricalResponse(_DictAccessMixin):
    """Response from GET /historical/{symbol}/."""

    symbol: Optional[str] = None
    interval: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    count: Optional[int] = None
    data: List[OHLCV] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HistoricalResponse":
        points = [OHLCV.from_dict(p) for p in d.get("data", [])]
        return cls(
            symbol=d.get("symbol"),
            interval=d.get("interval"),
            from_date=d.get("from"),
            to_date=d.get("to"),
            count=d.get("count"),
            data=points,
            raw=d,
        )


# ---------------------------------------------------------------------------
# Market
# ---------------------------------------------------------------------------

@dataclass
class MarketSummary(_DictAccessMixin):
    """Response from GET /market/summary/."""

    timestamp: Optional[str] = None
    index: Optional[str] = None
    is_delayed: Optional[bool] = None
    index_value: Optional[float] = None
    index_change: Optional[float] = None
    index_change_percent: Optional[float] = None
    total_volume: Optional[int] = None
    advancing: Optional[int] = None
    declining: Optional[int] = None
    unchanged: Optional[int] = None
    market_mood: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketSummary":
        return cls(
            timestamp=data.get("timestamp"),
            index=data.get("index"),
            is_delayed=data.get("is_delayed"),
            index_value=data.get("index_value"),
            index_change=data.get("index_change"),
            index_change_percent=data.get("index_change_percent"),
            total_volume=data.get("total_volume"),
            advancing=data.get("advancing"),
            declining=data.get("declining"),
            unchanged=data.get("unchanged"),
            market_mood=data.get("market_mood"),
            raw=data,
        )


@dataclass
class MarketMover(_DictAccessMixin):
    """A stock in gainers/losers/volume/value lists."""

    symbol: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    value: Optional[float] = None
    updated_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketMover":
        return cls(
            symbol=data.get("symbol"),
            name=data.get("name"),
            name_en=data.get("name_en"),
            price=data.get("price"),
            change=data.get("change"),
            change_percent=data.get("change_percent"),
            volume=data.get("volume"),
            value=data.get("value"),
            updated_at=data.get("updated_at"),
            raw=data,
        )


@dataclass
class MarketMoversResponse(_DictAccessMixin):
    """Response from gainers/losers/volume/value endpoints."""

    stocks: List[MarketMover] = field(default_factory=list)
    count: Optional[int] = None
    index: Optional[str] = None
    is_delayed: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], list_key: str = "stocks") -> "MarketMoversResponse":
        items = [MarketMover.from_dict(s) for s in data.get(list_key, [])]
        return cls(
            stocks=items,
            count=data.get("count"),
            index=data.get("index"),
            is_delayed=data.get("is_delayed"),
            raw=data,
        )


@dataclass
class Sector(_DictAccessMixin):
    """A sector from GET /market/sectors/."""

    id: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    change_percent: Optional[float] = None
    avg_change_percent: Optional[float] = None
    volume: Optional[int] = None
    num_stocks: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sector":
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            name_en=data.get("name_en"),
            change_percent=data.get("change_percent"),
            avg_change_percent=data.get("avg_change_percent"),
            volume=data.get("volume"),
            num_stocks=data.get("num_stocks"),
            raw=data,
        )


@dataclass
class SectorsResponse(_DictAccessMixin):
    """Response from GET /market/sectors/."""

    sectors: List[Sector] = field(default_factory=list)
    count: Optional[int] = None
    index: Optional[str] = None
    is_delayed: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SectorsResponse":
        items = [Sector.from_dict(s) for s in data.get("sectors", [])]
        return cls(
            sectors=items,
            count=data.get("count"),
            index=data.get("index"),
            is_delayed=data.get("is_delayed"),
            raw=data,
        )


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

@dataclass
class Fundamentals(_DictAccessMixin):
    """Company fundamentals (Starter+ plan)."""

    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    eps: Optional[float] = None
    book_value: Optional[float] = None
    price_to_book: Optional[float] = None
    beta: Optional[float] = None
    shares_outstanding: Optional[int] = None
    float_shares: Optional[int] = None
    week_high: Optional[float] = None
    week_low: Optional[float] = None
    month_high: Optional[float] = None
    month_low: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fundamentals":
        return cls(
            market_cap=data.get("market_cap"),
            pe_ratio=data.get("pe_ratio"),
            forward_pe=data.get("forward_pe"),
            eps=data.get("eps"),
            book_value=data.get("book_value"),
            price_to_book=data.get("price_to_book"),
            beta=data.get("beta"),
            shares_outstanding=data.get("shares_outstanding"),
            float_shares=data.get("float_shares"),
            week_high=data.get("week_high"),
            week_low=data.get("week_low"),
            month_high=data.get("month_high"),
            month_low=data.get("month_low"),
            fifty_two_week_high=data.get("fifty_two_week_high"),
            fifty_two_week_low=data.get("fifty_two_week_low"),
            raw=data,
        )


@dataclass
class Technicals(_DictAccessMixin):
    """Technical indicators (Pro plan)."""

    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    fifty_day_average: Optional[float] = None
    technical_strength: Optional[float] = None
    price_direction: Optional[str] = None
    updated_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Technicals":
        return cls(
            rsi_14=data.get("rsi_14"),
            macd_line=data.get("macd_line"),
            macd_signal=data.get("macd_signal"),
            macd_histogram=data.get("macd_histogram"),
            fifty_day_average=data.get("fifty_day_average"),
            technical_strength=data.get("technical_strength"),
            price_direction=data.get("price_direction"),
            updated_at=data.get("updated_at"),
            raw=data,
        )


@dataclass
class Valuation(_DictAccessMixin):
    """Proprietary fair-price valuation (Pro plan)."""

    fair_price: Optional[float] = None
    fair_price_confidence: Optional[float] = None
    calculated_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Valuation":
        return cls(
            fair_price=data.get("fair_price"),
            fair_price_confidence=data.get("fair_price_confidence"),
            calculated_at=data.get("calculated_at"),
            raw=data,
        )


@dataclass
class Analysts(_DictAccessMixin):
    """Analyst consensus data (Pro plan)."""

    target_mean: Optional[float] = None
    target_median: Optional[float] = None
    target_high: Optional[float] = None
    target_low: Optional[float] = None
    consensus: Optional[str] = None
    consensus_score: Optional[float] = None
    num_analysts: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Analysts":
        return cls(
            target_mean=data.get("target_mean"),
            target_median=data.get("target_median"),
            target_high=data.get("target_high"),
            target_low=data.get("target_low"),
            consensus=data.get("consensus"),
            consensus_score=data.get("consensus_score"),
            num_analysts=data.get("num_analysts"),
            raw=data,
        )


@dataclass
class Company(_DictAccessMixin):
    """Response from GET /company/{symbol}/. Fields vary by plan."""

    symbol: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    current_price: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    fundamentals: Optional[Fundamentals] = None
    technicals: Optional[Technicals] = None
    valuation: Optional[Valuation] = None
    analysts: Optional[Analysts] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Company":
        def _sub(key, klass):
            v = data.get(key)
            return klass.from_dict(v) if isinstance(v, dict) else None

        return cls(
            symbol=data.get("symbol"),
            name=data.get("name"),
            name_en=data.get("name_en"),
            current_price=data.get("current_price"),
            sector=data.get("sector"),
            industry=data.get("industry"),
            description=data.get("description"),
            website=data.get("website"),
            country=data.get("country"),
            currency=data.get("currency"),
            fundamentals=_sub("fundamentals", Fundamentals),
            technicals=_sub("technicals", Technicals),
            valuation=_sub("valuation", Valuation),
            analysts=_sub("analysts", Analysts),
            raw=data,
        )


# ---------------------------------------------------------------------------
# Financials
# ---------------------------------------------------------------------------

@dataclass
class IncomeStatement(_DictAccessMixin):
    """A single income statement period."""

    report_date: Optional[str] = None
    total_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncomeStatement":
        return cls(
            report_date=data.get("report_date"),
            total_revenue=data.get("total_revenue"),
            gross_profit=data.get("gross_profit"),
            operating_income=data.get("operating_income"),
            net_income=data.get("net_income"),
            raw=data,
        )


@dataclass
class BalanceSheet(_DictAccessMixin):
    """A single balance sheet period."""

    report_date: Optional[str] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    stockholders_equity: Optional[float] = None
    total_debt: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BalanceSheet":
        return cls(
            report_date=data.get("report_date"),
            total_assets=data.get("total_assets"),
            total_liabilities=data.get("total_liabilities"),
            stockholders_equity=data.get("stockholders_equity"),
            total_debt=data.get("total_debt"),
            raw=data,
        )


@dataclass
class CashFlow(_DictAccessMixin):
    """A single cash flow period."""

    report_date: Optional[str] = None
    operating_cash_flow: Optional[float] = None
    investing_cash_flow: Optional[float] = None
    financing_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CashFlow":
        return cls(
            report_date=data.get("report_date"),
            operating_cash_flow=data.get("operating_cash_flow"),
            investing_cash_flow=data.get("investing_cash_flow"),
            financing_cash_flow=data.get("financing_cash_flow"),
            free_cash_flow=data.get("free_cash_flow"),
            raw=data,
        )


@dataclass
class FinancialsResponse(_DictAccessMixin):
    """Response from GET /financials/{symbol}/."""

    symbol: Optional[str] = None
    income_statements: List[IncomeStatement] = field(default_factory=list)
    balance_sheets: List[BalanceSheet] = field(default_factory=list)
    cash_flows: List[CashFlow] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FinancialsResponse":
        return cls(
            symbol=data.get("symbol"),
            income_statements=[
                IncomeStatement.from_dict(i)
                for i in data.get("income_statements", [])
            ],
            balance_sheets=[
                BalanceSheet.from_dict(b)
                for b in data.get("balance_sheets", [])
            ],
            cash_flows=[
                CashFlow.from_dict(c)
                for c in data.get("cash_flows", [])
            ],
            raw=data,
        )


# ---------------------------------------------------------------------------
# Dividends
# ---------------------------------------------------------------------------

@dataclass
class DividendPayment(_DictAccessMixin):
    """A single dividend payment record."""

    value: Optional[float] = None
    value_percent: Optional[float] = None
    period: Optional[str] = None
    fiscal_year: Optional[int] = None
    announcement_date: Optional[str] = None
    eligibility_date: Optional[str] = None
    distribution_date: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DividendPayment":
        return cls(
            value=data.get("value"),
            value_percent=data.get("value_percent"),
            period=data.get("period"),
            fiscal_year=data.get("fiscal_year"),
            announcement_date=data.get("announcement_date"),
            eligibility_date=data.get("eligibility_date"),
            distribution_date=data.get("distribution_date"),
            raw=data,
        )


@dataclass
class DividendsResponse(_DictAccessMixin):
    """Response from GET /dividends/{symbol}/."""

    symbol: Optional[str] = None
    current_price: Optional[float] = None
    trailing_12m_yield: Optional[float] = None
    trailing_12m_dividends: Optional[float] = None
    payments_last_year: Optional[int] = None
    upcoming: List[DividendPayment] = field(default_factory=list)
    history: List[DividendPayment] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DividendsResponse":
        return cls(
            symbol=data.get("symbol"),
            current_price=data.get("current_price"),
            trailing_12m_yield=data.get("trailing_12m_yield"),
            trailing_12m_dividends=data.get("trailing_12m_dividends"),
            payments_last_year=data.get("payments_last_year"),
            upcoming=[
                DividendPayment.from_dict(u)
                for u in data.get("upcoming", [])
            ],
            history=[
                DividendPayment.from_dict(h)
                for h in data.get("history", [])
            ],
            raw=data,
        )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@dataclass
class Event(_DictAccessMixin):
    """A single stock event from GET /events/."""

    symbol: Optional[str] = None
    stock_name: Optional[str] = None
    event_type: Optional[str] = None
    importance: Optional[str] = None
    sentiment: Optional[str] = None
    description: Optional[str] = None
    article_date: Optional[str] = None
    created_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            symbol=data.get("symbol"),
            stock_name=data.get("stock_name"),
            event_type=data.get("event_type"),
            importance=data.get("importance"),
            sentiment=data.get("sentiment"),
            description=data.get("description"),
            article_date=data.get("article_date"),
            created_at=data.get("created_at"),
            raw=data,
        )


@dataclass
class EventsResponse(_DictAccessMixin):
    """Response from GET /events/."""

    events: List[Event] = field(default_factory=list)
    count: Optional[int] = None
    available_types: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventsResponse":
        return cls(
            events=[Event.from_dict(e) for e in data.get("events", [])],
            count=data.get("count"),
            available_types=data.get("available_types", []),
            raw=data,
        )
