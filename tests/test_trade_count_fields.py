"""Typed trade_count / value fields added in 0.17.1."""

import unittest

from sahmk.models import OHLCV, BatchQuote, MarketSummary, Quote


class TradeCountFieldTests(unittest.TestCase):
    def test_quote_trade_count_and_sizes(self):
        q = Quote.from_dict(
            {"symbol": "2222", "value": 1234.5, "trade_count": 812, "bid_size": 100, "ask_size": 250}
        )
        self.assertEqual(q.trade_count, 812)
        self.assertEqual(q.bid_size, 100)
        self.assertEqual(q.ask_size, 250)
        self.assertEqual(q.value, 1234.5)

    def test_quote_missing_trade_count_is_none(self):
        q = Quote.from_dict({"symbol": "2222", "trade_count": None})
        self.assertIsNone(q.trade_count)
        self.assertIsNone(q.bid_size)

    def test_batch_quote_value_and_trade_count(self):
        q = BatchQuote.from_dict({"symbol": "2222", "value": 99.0, "trade_count": 7})
        self.assertEqual(q.value, 99.0)
        self.assertEqual(q.trade_count, 7)

    def test_daily_bar_trade_count_fills_number_of_trades(self):
        bar = OHLCV.from_dict({"date": "2026-11-25", "turnover": 10.0, "trade_count": 42})
        self.assertEqual(bar.trade_count, 42)
        self.assertEqual(bar.number_of_trades, 42)
        self.assertEqual(bar.turnover, 10.0)

    def test_legacy_number_of_trades_fills_trade_count(self):
        bar = OHLCV.from_dict({"date": "2026-11-25T07:00:00+00:00", "number_of_trades": 5})
        self.assertEqual(bar.trade_count, 5)
        self.assertEqual(bar.number_of_trades, 5)

    def test_bar_without_counts(self):
        bar = OHLCV.from_dict({"date": "2026-11-25", "trade_count": None})
        self.assertIsNone(bar.trade_count)
        self.assertIsNone(bar.number_of_trades)
        self.assertNotIn("number_of_trades", bar)

    def test_market_summary_value_and_trade_count(self):
        m = MarketSummary.from_dict({"index": "TASI", "total_volume": 10, "value": 5.5, "trade_count": 3})
        self.assertEqual(m.value, 5.5)
        self.assertEqual(m.trade_count, 3)
        self.assertEqual(m["value"], 5.5)


if __name__ == "__main__":
    unittest.main()
