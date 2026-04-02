"""Unit tests for the CLI module."""

import json
import sys
import requests
from io import StringIO
from unittest import mock

import pytest
import responses
from sahmk.cli import main, _build_parser, _resolve_api_key, _print_json, _run_stream
from sahmk.client import SahmkError


class TestArgumentParser:
    """Tests for CLI argument parsing."""

    def test_parser_creation(self):
        """Test that parser is created successfully."""
        parser = _build_parser()
        assert parser is not None
        assert parser.prog == "sahmk"

    def test_parser_global_flags(self):
        """Test global flags are recognized."""
        parser = _build_parser()

        args = parser.parse_args(["--api-key", "test_key", "quote", "2222"])
        assert args.api_key == "test_key"

        args = parser.parse_args(["--base-url", "https://api.test", "quote", "2222"])
        assert args.base_url == "https://api.test"

        args = parser.parse_args(["--timeout", "60", "quote", "2222"])
        assert args.timeout == 60

    def test_parser_compact_flag_after_subcommand(self):
        """Test --compact works after the subcommand."""
        parser = _build_parser()
        args = parser.parse_args(["quote", "2222", "--compact"])
        assert args.compact is True

    def test_parser_quote_command(self):
        """Test quote command parsing."""
        parser = _build_parser()
        args = parser.parse_args(["quote", "2222"])
        
        assert args.command == "quote"
        assert args.symbol == "2222"

    def test_parser_quotes_command(self):
        """Test quotes command parsing."""
        parser = _build_parser()
        args = parser.parse_args(["quotes", "2222,1120,2010"])
        
        assert args.command == "quotes"
        assert args.symbols == "2222,1120,2010"

    def test_parser_market_commands(self):
        """Test market command parsing."""
        parser = _build_parser()
        
        # Test summary
        args = parser.parse_args(["market", "summary"])
        assert args.command == "market"
        assert args.view == "summary"
        
        # Test gainers
        args = parser.parse_args(["market", "gainers"])
        assert args.view == "gainers"
        
        # Test with limit
        args = parser.parse_args(["market", "gainers", "--limit", "5"])
        assert args.view == "gainers"
        assert args.limit == 5

    def test_parser_historical_command(self):
        """Test historical command parsing."""
        parser = _build_parser()
        args = parser.parse_args([
            "historical", "2222",
            "--from", "2024-01-01",
            "--to", "2024-01-10",
            "--interval", "1d"
        ])
        
        assert args.command == "historical"
        assert args.symbol == "2222"
        assert args.from_date == "2024-01-01"
        assert args.to_date == "2024-01-10"
        assert args.interval == "1d"


class TestResolveApiKey:
    """Tests for API key resolution."""

    def test_resolve_from_argument(self):
        """Test API key from CLI argument."""
        key = _resolve_api_key("cli_key")
        assert key == "cli_key"

    def test_resolve_from_environment(self, monkeypatch):
        """Test API key from environment variable."""
        monkeypatch.setenv("SAHMK_API_KEY", "env_key")
        key = _resolve_api_key(None)
        assert key == "env_key"

    def test_resolve_priority(self, monkeypatch):
        """Test CLI argument takes priority over env var."""
        monkeypatch.setenv("SAHMK_API_KEY", "env_key")
        key = _resolve_api_key("cli_key")
        assert key == "cli_key"

    def test_resolve_no_key(self, monkeypatch):
        """Test None when no key provided."""
        monkeypatch.delenv("SAHMK_API_KEY", raising=False)
        key = _resolve_api_key(None)
        assert key is None


class TestPrintJson:
    """Tests for JSON output formatting."""

    def test_print_json_pretty(self, capsys):
        """Test pretty JSON output."""
        data = {"key": "value", "number": 123}
        _print_json(data, compact=False)
        
        captured = capsys.readouterr()
        assert "{\n" in captured.out  # Has newlines for pretty print
        assert '"key": "value"' in captured.out

    def test_print_json_compact(self, capsys):
        """Test compact JSON output."""
        data = {"key": "value", "number": 123}
        _print_json(data, compact=True)
        
        captured = capsys.readouterr()
        # Compact should not have spaces after separators
        assert captured.out.strip() == '{"key":"value","number":123}'

    def test_print_json_unicode(self, capsys):
        """Test Unicode handling in JSON output."""
        data = {"arabic": "أرامكو"}
        _print_json(data, compact=False)
        
        captured = capsys.readouterr()
        assert "أرامكو" in captured.out


class TestMainQuoteCommand:
    """Tests for main function with quote command."""

    @responses.activate
    def test_quote_success(self, capsys, sample_quote_response):
        """Test successful quote command."""
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quote/2222/",
            json=sample_quote_response,
            status=200,
        )

        exit_code = main(["--api-key", "test_key", "quote", "2222"])
        
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "2222" in captured.out
        assert "Saudi Arabian Oil Co" in captured.out

    @responses.activate
    def test_quote_error(self, capsys):
        """Test quote command with API error."""
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quote/INVALID/",
            json={"error": {"code": "NOT_FOUND", "message": "Symbol not found"}},
            status=404,
        )

        exit_code = main(["--api-key", "test_key", "quote", "INVALID"])
        
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()

    def test_quote_no_api_key(self, capsys, monkeypatch):
        """Test quote command without API key."""
        monkeypatch.delenv("SAHMK_API_KEY", raising=False)
        
        with pytest.raises(SystemExit) as exc_info:
            main(["quote", "2222"])
        
        assert exc_info.value.code == 2  # argparse exit code for error


class TestMainQuotesCommand:
    """Tests for main function with quotes command."""

    @responses.activate
    def test_quotes_success(self, capsys, sample_quotes_response):
        """Test successful quotes command."""
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quotes/",
            json=sample_quotes_response,
            status=200,
        )

        exit_code = main(["--api-key", "test_key", "quotes", "2222,1120"])
        
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "2222" in captured.out
        assert "1120" in captured.out

    @responses.activate
    def test_quotes_empty_symbols(self, capsys, monkeypatch):
        """Test quotes command with empty symbols."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        
        with pytest.raises(SystemExit) as exc_info:
            main(["quotes", ""])
        
        assert exc_info.value.code == 2

    @responses.activate
    def test_quotes_whitespace_symbols(self, capsys, sample_quotes_response, monkeypatch):
        """Test quotes command with whitespace in symbols."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quotes/",
            json=sample_quotes_response,
            status=200,
        )

        exit_code = main(["quotes", "  2222  ,  1120  "])
        
        assert exit_code == 0


class TestMainMarketCommand:
    """Tests for main function with market command."""

    @responses.activate
    def test_market_summary(self, capsys, sample_market_summary_response, monkeypatch):
        """Test market summary command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/market/summary/",
            json=sample_market_summary_response,
            status=200,
        )

        exit_code = main(["market", "summary"])
        
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "11950.35" in captured.out

    @responses.activate
    def test_market_gainers(self, capsys, sample_gainers_response, monkeypatch):
        """Test market gainers command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/market/gainers/",
            json=sample_gainers_response,
            status=200,
        )

        exit_code = main(["market", "gainers", "--limit", "5"])
        
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "gainers" in captured.out.lower() or "1234" in captured.out

    @responses.activate
    def test_market_losers(self, capsys, sample_losers_response, monkeypatch):
        """Test market losers command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/market/losers/",
            json=sample_losers_response,
            status=200,
        )

        exit_code = main(["market", "losers"])
        
        assert exit_code == 0

    @responses.activate
    def test_market_volume(self, capsys, sample_volume_leaders_response, monkeypatch):
        """Test market volume command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/market/volume/",
            json=sample_volume_leaders_response,
            status=200,
        )

        exit_code = main(["market", "volume"])
        
        assert exit_code == 0

    @responses.activate
    def test_market_value(self, capsys, sample_value_leaders_response, monkeypatch):
        """Test market value command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/market/value/",
            json=sample_value_leaders_response,
            status=200,
        )

        exit_code = main(["market", "value"])
        
        assert exit_code == 0

    @responses.activate
    def test_market_sectors(self, capsys, sample_sectors_response, monkeypatch):
        """Test market sectors command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/market/sectors/",
            json=sample_sectors_response,
            status=200,
        )

        exit_code = main(["market", "sectors"])
        
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "sectors" in captured.out.lower() or "البنوك" in captured.out


class TestMainHistoricalCommand:
    """Tests for main function with historical command."""

    @responses.activate
    def test_historical_basic(self, capsys, sample_historical_response, monkeypatch):
        """Test historical command with basic args."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/historical/2222/",
            json=sample_historical_response,
            status=200,
        )

        exit_code = main(["historical", "2222"])
        
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "2222" in captured.out
        assert "data" in captured.out

    @responses.activate
    def test_historical_full_args(self, capsys, sample_historical_response, monkeypatch):
        """Test historical command with all args."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/historical/2222/",
            json=sample_historical_response,
            status=200,
        )

        exit_code = main([
            "historical", "2222",
            "--from", "2024-01-01",
            "--to", "2024-01-10",
            "--interval", "1d"
        ])
        
        assert exit_code == 0


class TestMainErrorHandling:
    """Tests for error handling in main function."""

    @responses.activate
    def test_network_error_output(self, capsys, monkeypatch):
        """Test error output format for network errors."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quote/2222/",
            body=requests.ConnectionError("Connection refused"),
        )

        exit_code = main(["quote", "2222"])
        
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()

    @responses.activate
    def test_api_error_with_code(self, capsys, monkeypatch):
        """Test error output includes error code."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quote/2222/",
            json={"error": {"code": "INVALID_KEY", "message": "Invalid API key"}},
            status=401,
        )

        exit_code = main(["quote", "2222"])
        
        assert exit_code == 1
        captured = capsys.readouterr()
        err_data = json.loads(captured.err)
        assert err_data["code"] == "INVALID_KEY"

    @responses.activate
    def test_api_error_with_status_code(self, capsys, monkeypatch):
        """Test error output includes HTTP status code."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quote/2222/",
            json={"error": {"code": "NOT_FOUND", "message": "Symbol not found"}},
            status=404,
        )

        exit_code = main(["quote", "2222"])
        
        assert exit_code == 1
        captured = capsys.readouterr()
        err_data = json.loads(captured.err)
        assert err_data["status_code"] == 404


class TestMainCompactOutput:
    """Tests for compact JSON output option."""

    @responses.activate
    def test_compact_output(self, capsys, sample_quote_response):
        """Test --compact produces compact JSON."""
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quote/2222/",
            json=sample_quote_response,
            status=200,
        )

        exit_code = main(["--api-key", "test_key", "quote", "2222", "--compact"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "\n  " not in captured.out

    @responses.activate
    def test_non_compact_output(self, capsys, sample_quote_response):
        """Test default (non-compact) output is indented."""
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/quote/2222/",
            json=sample_quote_response,
            status=200,
        )

        exit_code = main(["--api-key", "test_key", "quote", "2222"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "\n  " in captured.out


class TestMainCompanyCommand:
    """Tests for main function with company command."""

    @responses.activate
    def test_company_success(self, capsys, sample_company_response, monkeypatch):
        """Test successful company command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/company/2222/",
            json=sample_company_response,
            status=200,
        )

        exit_code = main(["company", "2222"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "2222" in captured.out
        assert "Saudi Arabian Oil Co" in captured.out


class TestMainFinancialsCommand:
    """Tests for main function with financials command."""

    @responses.activate
    def test_financials_success(self, capsys, sample_financials_response, monkeypatch):
        """Test successful financials command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/financials/2222/",
            json=sample_financials_response,
            status=200,
        )

        exit_code = main(["financials", "2222"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "income_statements" in captured.out


class TestMainDividendsCommand:
    """Tests for main function with dividends command."""

    @responses.activate
    def test_dividends_success(self, capsys, sample_dividends_response, monkeypatch):
        """Test successful dividends command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/dividends/2222/",
            json=sample_dividends_response,
            status=200,
        )

        exit_code = main(["dividends", "2222"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "trailing_12m_yield" in captured.out


class TestMainEventsCommand:
    """Tests for main function with events command."""

    @responses.activate
    def test_events_success(self, capsys, sample_events_response, monkeypatch):
        """Test successful events command."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/events/",
            json=sample_events_response,
            status=200,
        )

        exit_code = main(["events"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "events" in captured.out

    @responses.activate
    def test_events_with_symbol(self, capsys, sample_events_response, monkeypatch):
        """Test events command with --symbol filter."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/events/",
            json=sample_events_response,
            status=200,
        )

        exit_code = main(["events", "--symbol", "2222"])

        assert exit_code == 0
        request = responses.calls[0].request
        assert "symbol=2222" in request.url

    @responses.activate
    def test_events_with_limit(self, capsys, sample_events_response, monkeypatch):
        """Test events command with --limit."""
        monkeypatch.setenv("SAHMK_API_KEY", "test_key")
        responses.add(
            responses.GET,
            "https://app.sahmk.sa/api/v1/events/",
            json=sample_events_response,
            status=200,
        )

        exit_code = main(["events", "--limit", "5"])

        assert exit_code == 0
        request = responses.calls[0].request
        assert "limit=5" in request.url


class TestParserNewCommands:
    """Tests for parsing new CLI commands."""

    def test_parser_company_command(self):
        parser = _build_parser()
        args = parser.parse_args(["company", "2222"])
        assert args.command == "company"
        assert args.symbol == "2222"

    def test_parser_financials_command(self):
        parser = _build_parser()
        args = parser.parse_args(["financials", "2222"])
        assert args.command == "financials"
        assert args.symbol == "2222"

    def test_parser_dividends_command(self):
        parser = _build_parser()
        args = parser.parse_args(["dividends", "2222"])
        assert args.command == "dividends"
        assert args.symbol == "2222"

    def test_parser_events_command(self):
        parser = _build_parser()
        args = parser.parse_args(["events", "--symbol", "2222", "--limit", "10"])
        assert args.command == "events"
        assert args.symbol == "2222"
        assert args.limit == 10

    def test_parser_events_no_args(self):
        parser = _build_parser()
        args = parser.parse_args(["events"])
        assert args.command == "events"
        assert args.symbol is None
        assert args.limit is None

    def test_parser_stream_command(self):
        parser = _build_parser()
        args = parser.parse_args(["stream", "2222,1120"])
        assert args.command == "stream"
        assert args.symbols == "2222,1120"
