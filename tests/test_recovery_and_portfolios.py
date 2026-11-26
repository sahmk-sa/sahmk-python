"""Tests for historical intervals, trades recovery, writes, and portfolios."""

import json

import pytest
import requests
import responses
from sahmk import SahmkClient, SahmkError, SahmkRateLimitError, TradesPage
from sahmk.client import HISTORICAL_INTERVAL_ALIASES, HISTORICAL_INTERVALS

BASE = "https://mock-api.sahmk.sa/api/v1"


@pytest.fixture
def client():
    return SahmkClient(api_key="shmk_test", base_url=BASE, retries=3, backoff_factor=0.01)


def _dated_trades_page(events, has_more, next_cursor=None, last_seq=None):
    return {
        "symbol": "2222",
        "count": len(events),
        "events": events,
        "summary": {"event_count": len(events)},
        "page": {
            "limit": 2,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "last_trade_seq": last_seq,
            "order": "receive",
            "recovery": "sequence_filter",
            "complete_official_volume": False,
            "scan_capped": False,
        },
    }


class TestHistoricalIntervals:
    def test_canonical_intervals_match_backend(self):
        assert HISTORICAL_INTERVALS == (
            "1min", "5min", "15min", "30min", "60min", "1d", "1w", "1mo",
        )
        assert HISTORICAL_INTERVAL_ALIASES == {"30m": "30min", "60m": "60min", "1m": "1mo"}

    @responses.activate
    @pytest.mark.parametrize("interval", ["1min", "5min", "15min", "1mo"])
    def test_new_intervals_are_sent(self, client, interval):
        responses.add(responses.GET, f"{BASE}/historical/2222/", json={"symbol": "2222", "data": []})
        client.historical("2222", interval=interval)
        assert f"interval={interval}" in responses.calls[0].request.url

    @responses.activate
    def test_limit_and_offset_are_sent(self, client):
        responses.add(responses.GET, f"{BASE}/historical/2222/", json={"symbol": "2222", "data": []})
        client.historical("2222", interval="5min", limit=2000, offset=500)
        url = responses.calls[0].request.url
        assert "limit=2000" in url
        assert "offset=500" in url

    @pytest.mark.parametrize("kwargs", [{"limit": 0}, {"offset": -1}, {"offset": "1"}])
    def test_limit_offset_validated(self, client, kwargs):
        with pytest.raises(ValueError):
            client.historical("2222", **kwargs)


class TestTradesRecovery:
    @responses.activate
    def test_dated_call_sends_params_and_parses_page(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/market/trades/2222/",
            json=_dated_trades_page(
                [{"trade_seq": 204506, "price": 26.6, "market_session": "REGULAR"}],
                has_more=True,
                next_cursor="abc",
                last_seq=204506,
            ),
        )
        result = client.trades("2222", limit=50, date="2026-11-22", after_seq=204505)

        url = responses.calls[0].request.url
        assert "date=2026-11-22" in url
        assert "after_seq=204505" in url
        assert "limit=50" in url
        assert isinstance(result.page, TradesPage)
        assert result.page.has_more is True
        assert result.page.next_cursor == "abc"
        assert result.page.complete_official_volume is False
        assert result.events[0].trade_seq == 204506
        assert result.events[0].market_session == "REGULAR"

    @responses.activate
    def test_undated_call_has_no_page(self, client, sample_trades_response):
        responses.add(responses.GET, f"{BASE}/market/trades/2222/", json=sample_trades_response)
        result = client.trades("2222")
        assert result.page is None
        assert "date=" not in responses.calls[0].request.url

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"after_seq": 1}, "date"),
            ({"cursor": "abc"}, "date"),
            ({"date": "22-11-2026"}, "YYYY-MM-DD"),
            ({"date": "2026-11-22", "after_seq": -1}, "non-negative"),
            ({"date": "2026-11-22", "after_seq": "x"}, "non-negative"),
            ({"date": "2026-11-22", "after_seq": True}, "non-negative"),
        ],
    )
    def test_recovery_params_validated(self, client, kwargs, message):
        with pytest.raises(ValueError, match=message):
            client.trades("2222", **kwargs)

    @responses.activate
    def test_iter_trades_follows_cursor(self, client):
        url = f"{BASE}/market/trades/2222/"
        responses.add(
            responses.GET,
            url,
            json=_dated_trades_page([{"trade_seq": 1}, {"trade_seq": 2}], True, "c1", 2),
        )
        responses.add(
            responses.GET,
            url,
            json=_dated_trades_page([{"trade_seq": 3}], False, None, 3),
        )

        seqs = [event.trade_seq for event in client.iter_trades("2222", "2026-11-22", limit=2)]

        assert seqs == [1, 2, 3]
        assert "cursor" not in responses.calls[0].request.url
        assert "cursor=c1" in responses.calls[1].request.url
        assert all("date=2026-11-22" in call.request.url for call in responses.calls)

    @responses.activate
    def test_iter_trades_respects_max_pages(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/market/trades/2222/",
            json=_dated_trades_page([{"trade_seq": 1}], True, "c1", 1),
        )
        events = list(client.iter_trades("2222", "2026-11-22", max_pages=1))
        assert len(events) == 1
        assert len(responses.calls) == 1


class TestWriteRequests:
    @responses.activate
    def test_post_sends_json_and_accepts_201(self, client):
        responses.add(responses.POST, f"{BASE}/portfolios/", json={"id": 7, "name": "Core"}, status=201)
        result = client.create_portfolio("Core", description="Long term")
        assert result == {"id": 7, "name": "Core"}
        assert json.loads(responses.calls[0].request.body) == {
            "name": "Core",
            "description": "Long term",
        }

    @responses.activate
    def test_delete_204_returns_none(self, client):
        responses.add(responses.DELETE, f"{BASE}/portfolios/7/", status=204)
        assert client.delete_portfolio(7) is None

    @responses.activate
    def test_write_not_retried_on_503(self, client):
        url = f"{BASE}/portfolios/7/transactions/"
        responses.add(responses.POST, url, body="Service Unavailable", status=503)
        responses.add(responses.POST, url, json={"id": 1}, status=201)
        with pytest.raises(SahmkError) as exc_info:
            client.create_portfolio_transaction(7, "deposit", 1000)
        assert exc_info.value.status_code == 503
        assert len(responses.calls) == 1

    @responses.activate
    def test_write_not_retried_on_timeout(self, client):
        responses.add(
            responses.POST,
            f"{BASE}/portfolios/7/transactions/",
            body=requests.Timeout("slow"),
        )
        with pytest.raises(SahmkError, match="timed out"):
            client.create_portfolio_transaction(7, "deposit", 1000)
        assert len(responses.calls) == 1

    @responses.activate
    def test_write_retried_on_429(self, client):
        url = f"{BASE}/portfolios/"
        responses.add(responses.POST, url, status=429, headers={"Retry-After": "0"})
        responses.add(responses.POST, url, json={"id": 1}, status=201)
        assert client.create_portfolio("Core") == {"id": 1}
        assert len(responses.calls) == 2

    @responses.activate
    def test_write_429_exhausted_raises_rate_limit(self, client):
        url = f"{BASE}/portfolios/"
        for _ in range(4):
            responses.add(responses.POST, url, status=429, headers={"Retry-After": "0"})
        with pytest.raises(SahmkRateLimitError):
            client.create_portfolio("Core")

    @responses.activate
    def test_validation_errors_are_exposed(self, client):
        responses.add(
            responses.POST,
            f"{BASE}/portfolios/7/transactions/",
            json={
                "error": {
                    "code": "validation_error",
                    "errors": {"symbol": ["This field is required."]},
                }
            },
            status=400,
        )
        with pytest.raises(SahmkError) as exc_info:
            client.create_portfolio_transaction(7, "buy", 100)
        assert exc_info.value.error_code == "validation_error"
        assert exc_info.value.errors == {"symbol": ["This field is required."]}
        assert "symbol" in str(exc_info.value)

    @responses.activate
    def test_top_level_portfolio_error_shape(self, client):
        """Live portfolio API shape: error fields at the top level, no "error" key."""
        responses.add(
            responses.POST,
            f"{BASE}/portfolios/7/transactions/",
            json={
                "success": False,
                "code": "validation_error",
                "errors": {"transaction_type": ['"gift" is not a valid choice.']},
            },
            status=400,
        )
        with pytest.raises(SahmkError) as exc_info:
            client.create_portfolio_transaction(7, "gift", 1)
        err = exc_info.value
        assert err.status_code == 400
        assert err.error_code == "validation_error"
        assert err.errors == {"transaction_type": ['"gift" is not a valid choice.']}
        assert str(err).startswith("API error 400: validation_error ")
        assert '"success"' not in str(err)

    @responses.activate
    def test_top_level_error_with_message(self, client):
        responses.add(
            responses.POST,
            f"{BASE}/portfolios/",
            json={"success": False, "code": "duplicate_portfolio_name", "message": "A portfolio with this name already exists."},
            status=400,
        )
        with pytest.raises(SahmkError) as exc_info:
            client.create_portfolio("Core")
        assert exc_info.value.error_code == "duplicate_portfolio_name"
        assert exc_info.value.errors is None
        assert str(exc_info.value) == "API error 400: A portfolio with this name already exists."


class TestPortfolios:
    @responses.activate
    def test_list_with_workspace(self, client):
        responses.add(responses.GET, f"{BASE}/portfolios/", json={"count": 0, "portfolios": []})
        assert client.portfolios(workspace_id=3) == {"count": 0, "portfolios": []}
        assert "workspace_id=3" in responses.calls[0].request.url

    @responses.activate
    def test_read_endpoints(self, client):
        responses.add(responses.GET, f"{BASE}/portfolios/7/", json={"id": 7})
        responses.add(responses.GET, f"{BASE}/portfolios/7/transactions/", json={"count": 0, "transactions": []})
        responses.add(responses.GET, f"{BASE}/portfolios/7/holdings/summary/", json={"cash_sar": 0})
        responses.add(responses.GET, f"{BASE}/portfolios/7/performance/", json={"points": []})

        assert client.portfolio(7) == {"id": 7}
        assert client.portfolio_transactions(7)["count"] == 0
        assert client.portfolio_summary(7) == {"cash_sar": 0}
        client.portfolio_performance(7, days=90)
        assert "days=90" in responses.calls[3].request.url

    @responses.activate
    def test_update_sends_only_passed_fields(self, client):
        responses.add(responses.PATCH, f"{BASE}/portfolios/7/", json={"id": 7, "name": "New"})
        client.update_portfolio(7, name="New")
        assert json.loads(responses.calls[0].request.body) == {"name": "New"}

    def test_update_requires_a_field(self, client):
        with pytest.raises(ValueError, match="at least one"):
            client.update_portfolio(7)

    @responses.activate
    def test_single_transaction_body(self, client):
        responses.add(responses.POST, f"{BASE}/portfolios/7/transactions/", json={"id": 1}, status=201)
        client.create_portfolio_transaction(
            7,
            "BUY",
            2660,
            symbol="2222",
            quantity=100,
            unit_price_sar=26.6,
            idempotency_key="k1",
        )
        assert json.loads(responses.calls[0].request.body) == {
            "transaction_type": "buy",
            "amount_sar": 2660,
            "symbol": "2222",
            "quantity": 100,
            "unit_price_sar": 26.6,
            "idempotency_key": "k1",
        }

    @responses.activate
    def test_batch_transaction_body(self, client):
        responses.add(responses.POST, f"{BASE}/portfolios/7/transactions/", json={"created": 2}, status=201)
        txs = [
            {"transaction_type": "deposit", "amount_sar": 1000},
            {"transaction_type": "fee", "amount_sar": 5},
        ]
        client.create_portfolio_transactions(7, txs, "batch-1")
        assert json.loads(responses.calls[0].request.body) == {
            "transactions": txs,
            "batch_idempotency_key": "batch-1",
        }

    def test_batch_requires_key_and_items(self, client):
        with pytest.raises(ValueError, match="batch_idempotency_key"):
            client.create_portfolio_transactions(7, [{"transaction_type": "deposit"}], " ")
        with pytest.raises(ValueError, match="non-empty"):
            client.create_portfolio_transactions(7, [], "k")

    @responses.activate
    def test_reverse_transaction(self, client):
        responses.add(
            responses.POST,
            f"{BASE}/portfolios/7/transactions/9/reverse/",
            json={"id": 10},
            status=201,
        )
        client.reverse_portfolio_transaction(7, 9, notes="typo")
        assert json.loads(responses.calls[0].request.body) == {"notes": "typo"}

    @responses.activate
    def test_set_holdings_dry_run_then_apply(self, client):
        url = f"{BASE}/portfolios/7/holdings/set/"
        responses.add(responses.POST, url, json={"success": True, "dry_run": True, "plan": {"plan_token": "t"}})
        responses.add(responses.POST, url, json={"success": True, "dry_run": False, "result": {}}, status=201)
        holdings = [{"symbol": "2222", "quantity": 100, "avg_cost_sar": 26.0}]

        plan = client.set_portfolio_holdings(7, holdings, "partial", "auto_fund")
        client.set_portfolio_holdings(
            7,
            holdings,
            "partial",
            "auto_fund",
            dry_run=False,
            plan_token=plan["plan"]["plan_token"],
            expected_latest_transaction_id=12,
        )

        assert json.loads(responses.calls[0].request.body) == {
            "holdings": holdings,
            "scope": "partial",
            "cash_policy": "auto_fund",
            "dry_run": True,
        }
        assert json.loads(responses.calls[1].request.body) == {
            "holdings": holdings,
            "scope": "partial",
            "cash_policy": "auto_fund",
            "dry_run": False,
            "plan_token": "t",
            "expected_latest_transaction_id": 12,
        }

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"scope": "all"}, "scope"),
            ({"cash_policy": "magic"}, "cash_policy"),
            ({"dry_run": False}, "plan_token"),
        ],
    )
    def test_set_holdings_validation(self, client, kwargs, message):
        args = {"scope": "full", "cash_policy": "require_cash"}
        args.update(kwargs)
        with pytest.raises(ValueError, match=message):
            client.set_portfolio_holdings(7, [], **args)

    @pytest.mark.parametrize("bad", [0, -1, "x", True, None])
    def test_portfolio_id_must_be_positive_int(self, client, bad):
        with pytest.raises(ValueError, match="portfolio_id"):
            client.portfolio(bad)
