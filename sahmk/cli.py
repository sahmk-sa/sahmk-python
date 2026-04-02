"""
Command-line interface for the SAHMK Python SDK.
"""

import argparse
import json
import os
import sys

from .client import SahmkClient, SahmkError


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
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON output.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    quote_parser = subparsers.add_parser("quote", help="Get a single stock quote.")
    quote_parser.add_argument("symbol", help='Stock symbol (e.g., "2222").')

    quotes_parser = subparsers.add_parser(
        "quotes", help="Get quotes for multiple symbols."
    )
    quotes_parser.add_argument(
        "symbols",
        help='Comma-separated symbols, e.g. "2222,1120,2010".',
    )

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

    return parser


def _resolve_api_key(cli_api_key):
    return cli_api_key or os.environ.get("SAHMK_API_KEY")


def _print_json(payload, compact=False):
    data = getattr(payload, "raw", payload)
    if compact:
        print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))


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
