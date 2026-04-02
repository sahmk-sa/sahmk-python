"""
Command-line interface for the SAHMK Python SDK.
"""

import argparse
import asyncio
import json
import os
import sys

from .client import SahmkClient, SahmkError


def _compact_arg(parser):
    """Add --compact flag to a parser."""
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON output.",
    )


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="sahmk",
        description="CLI for the SAHMK Developer API",
    )
    parser.add_argument(
        "--api-key",
        help="SAHMK API key. Defaults to SAHMK_API_KEY environment variable.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override API base URL (optional).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    quote_parser = subparsers.add_parser("quote", help="Get a single stock quote.")
    quote_parser.add_argument("symbol", help='Stock symbol (e.g., "2222").')
    _compact_arg(quote_parser)

    quotes_parser = subparsers.add_parser(
        "quotes", help="Get quotes for multiple symbols."
    )
    quotes_parser.add_argument(
        "symbols",
        help='Comma-separated symbols, e.g. "2222,1120,2010".',
    )
    _compact_arg(quotes_parser)

    market_parser = subparsers.add_parser("market", help="Market overview endpoints.")
    market_parser.add_argument(
        "view",
        choices=["summary", "gainers", "losers", "volume", "value", "sectors"],
        help="Market data view.",
    )
    market_parser.add_argument(
        "--limit",
        type=int,
        help="Optional limit for gainers/losers/volume/value.",
    )
    _compact_arg(market_parser)

    historical_parser = subparsers.add_parser(
        "historical", help="Get historical OHLCV data."
    )
    historical_parser.add_argument("symbol", help='Stock symbol (e.g., "2222").')
    historical_parser.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD.")
    historical_parser.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD.")
    historical_parser.add_argument(
        "--interval",
        choices=["1d", "1w", "1m"],
        help='Interval: "1d", "1w", or "1m".',
    )
    _compact_arg(historical_parser)

    company_parser = subparsers.add_parser(
        "company", help="Get company info (tiered by plan)."
    )
    company_parser.add_argument("symbol", help='Stock symbol (e.g., "2222").')
    _compact_arg(company_parser)

    financials_parser = subparsers.add_parser(
        "financials", help="Get financial statements (Starter+ plan)."
    )
    financials_parser.add_argument("symbol", help='Stock symbol (e.g., "2222").')
    _compact_arg(financials_parser)

    dividends_parser = subparsers.add_parser(
        "dividends", help="Get dividend history and yield (Starter+ plan)."
    )
    dividends_parser.add_argument("symbol", help='Stock symbol (e.g., "2222").')
    _compact_arg(dividends_parser)

    events_parser = subparsers.add_parser(
        "events", help="Get AI-generated stock events (Pro+ plan)."
    )
    events_parser.add_argument(
        "--symbol",
        default=None,
        help="Filter events for a specific stock symbol.",
    )
    events_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of events to return.",
    )
    _compact_arg(events_parser)

    stream_parser = subparsers.add_parser(
        "stream", help="Stream real-time quotes via WebSocket (Pro+ plan)."
    )
    stream_parser.add_argument(
        "symbols",
        help='Comma-separated symbols to stream, e.g. "2222,1120".',
    )

    return parser


def _resolve_api_key(cli_api_key):
    return cli_api_key or os.environ.get("SAHMK_API_KEY")


def _print_json(payload, compact=False):
    data = getattr(payload, "raw", payload)
    if compact:
        print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _run_stream(client, symbols):
    """Run the WebSocket stream, printing quotes as JSON lines."""

    async def on_quote(msg):
        symbol = msg.get("symbol", "?")
        data = msg.get("data", {})
        line = json.dumps(
            {"symbol": symbol, **data},
            ensure_ascii=False,
        )
        print(line, flush=True)

    async def on_error(error):
        err_msg = error.get("message", str(error))
        print(
            json.dumps({"error": err_msg}, ensure_ascii=False),
            file=sys.stderr,
            flush=True,
        )

    async def on_disconnect(reason):
        print(
            json.dumps({"status": "disconnected", "reason": reason}, ensure_ascii=False),
            file=sys.stderr,
            flush=True,
        )

    async def on_reconnect(attempt):
        print(
            json.dumps({"status": "reconnecting", "attempt": attempt}, ensure_ascii=False),
            file=sys.stderr,
            flush=True,
        )

    async def _stream():
        await client.stream(
            symbols,
            on_quote=on_quote,
            on_error=on_error,
            on_disconnect=on_disconnect,
            on_reconnect=on_reconnect,
        )

    try:
        asyncio.run(_stream())
    except KeyboardInterrupt:
        pass


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    api_key = _resolve_api_key(args.api_key)
    if not api_key:
        parser.error("API key is required. Pass --api-key or set SAHMK_API_KEY.")

    client = SahmkClient(
        api_key=api_key,
        base_url=args.base_url,
        timeout=args.timeout,
    )

    try:
        if args.command == "quote":
            result = client.quote(args.symbol)
        elif args.command == "quotes":
            symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
            if not symbols:
                parser.error("At least one symbol is required for quotes.")
            result = client.quotes(symbols)
        elif args.command == "market":
            if args.view == "summary":
                result = client.market_summary()
            elif args.view == "gainers":
                result = client.gainers(limit=args.limit)
            elif args.view == "losers":
                result = client.losers(limit=args.limit)
            elif args.view == "volume":
                result = client.volume_leaders(limit=args.limit)
            elif args.view == "value":
                result = client.value_leaders(limit=args.limit)
            else:
                result = client.sectors()
        elif args.command == "historical":
            result = client.historical(
                args.symbol,
                from_date=args.from_date,
                to_date=args.to_date,
                interval=args.interval,
            )
        elif args.command == "company":
            result = client.company(args.symbol)
        elif args.command == "financials":
            result = client.financials(args.symbol)
        elif args.command == "dividends":
            result = client.dividends(args.symbol)
        elif args.command == "events":
            result = client.events(symbol=args.symbol, limit=args.limit)
        elif args.command == "stream":
            symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
            if not symbols:
                parser.error("At least one symbol is required for stream.")
            _run_stream(client, symbols)
            return 0
        else:
            parser.error("Unknown command.")
            return 2
    except SahmkError as exc:
        err = {"error": str(exc)}
        if exc.error_code:
            err["code"] = exc.error_code
        if exc.status_code:
            err["status_code"] = exc.status_code
        print(json.dumps(err, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    _print_json(result, compact=args.compact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
