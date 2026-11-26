# SAHMK Python SDK

[![Official Source](https://img.shields.io/badge/Source-Official%20Only-0A66C2?style=for-the-badge)](https://github.com/sahmk-sa/sahmk-python)

> **Official distribution:** GitHub (sahmk-sa) and PyPI only. Do not download binaries from third-party forks.

Official Python SDK for [Sahmk](https://sahmk.sa/developers) — Saudi market data and richer market workflows for developers.

Use one client for live Tadawul quotes, market-level insights, company/fundamental data, financials, events, and historical series.

## Features

- **Real-time quotes** for 350+ Tadawul stocks
- **Batch quotes** for up to 50 symbols per request
- **Historical and intraday OHLCV** (`1min`, `5min`, `15min`, `30min`, `60min`, `1d`, `1w`, `1mo`; plan-limited)
- **Market overview** with index scoping (`TASI`/`NOMU`)
- **Market depth** order book snapshots (entitlement-gated)
- **Live trades** recent prints, per-session recovery with cursor paging, and real-time tape (Pro+)
- **Company directory** endpoint for symbol discovery
- **Company/fundamental** data (plan-dependent fields)
- **Financials, dividends, and events** endpoints (by plan)
- **WebSocket streaming** for quotes, depth, and trades (Pro+/entitled)
- **Portfolios**: create, record transactions, reconcile holdings, and read P&L and performance

## Installation

```bash
pip install sahmk
```

For local development:

```bash
git clone https://github.com/sahmk-sa/sahmk-python.git
cd sahmk-python
pip install -r requirements.txt
```

## Security

- Use environment variables for API keys (recommended: `SAHMK_API_KEY`).
- Never commit API keys to source control, notebooks, or logs.
- If a key is exposed, rotate it immediately from your Sahmk dashboard.

## Quick Start

```python
import os
from sahmk import SahmkClient

client = SahmkClient(os.environ["SAHMK_API_KEY"])

quote = client.quote("2222")
print(f"{quote['name_en']}: {quote['price']} SAR ({quote['change_percent']}%)")

market = client.market_summary(index="TASI")
print(f"TASI: {market['index_value']} ({market['index_change_percent']}%)")

# Batch quotes are Starter+ plan.
for q in client.quotes(["2222", "1120", "7010"])["quotes"]:
    print(f"{q['symbol']}: {q['price']}")
```

## Identifier Resolution (Quotes)

`quote()` and `quotes()` accept either traditional symbols or resolvable identifiers:

- Symbol: `"2222"`
- Arabic company name: `"أرامكو السعودية"`
- English company name/alias: `"Aramco"`

Symbol input always works. Name/alias input requires backend identifier-resolution support.
For batch quotes, the SDK first tries `identifiers=...`, then automatically falls back to
legacy `symbols=...` when connected to older backends.

```python
q1 = client.quote("2222")              # classic symbol usage
q2 = client.quote("أرامكو السعودية")   # Arabic identifier
q3 = client.quote("Aramco")            # English alias

batch = client.quotes(["2222", "الراجحي", "SABIC"])
for q in batch.quotes:
    print(q.requested_identifier, "=>", q.symbol)

if batch.ambiguous:
    print("Ambiguous:", batch.ambiguous)
if batch.unknown:
    print("Unknown:", batch.unknown)
```

When the backend returns resolution metadata, it is exposed on typed objects:

```python
quote = client.quote("Aramco")
print(quote.requested_identifier)      # Aramco
print(quote.resolved_symbol)           # 2222
print(quote.resolution.matched_by)     # alias (if provided by API)
```

## Company Directory / Symbol Discovery

Use `companies()` as the canonical symbol-discovery path before calling
`quote()` or `company()`.

```python
# Search by symbol or name
directory = client.companies(search="aram")
for row in directory["results"]:
    print(row["symbol"], row.get("name_en") or row.get("name"))
```

```python
# Filter by market (TASI / NOMU, NOMUC alias is accepted)
nomu_companies = client.companies(market="NOMUC", limit=20)
print(nomu_companies["count"])
```

```python
# Pagination loop with offset
offset = 0
page_size = 100

while True:
    page = client.companies(limit=page_size, offset=offset)
    for company in page["results"]:
        print(company["symbol"])

    offset += page_size
    if offset >= page["total"]:
        break
```

Recommended flow:

1. Discover valid symbols with `companies()`.
2. Call `quote(symbol)` / `company(symbol)` with a validated symbol.

## Production Reliability

- The client retries transient failures: **HTTP 429** and **5xx** errors, and timeouts.
- Writes (POST, PATCH, DELETE) are retried only on **429**. A write that timed out or got a 5xx may already have been applied, so it is raised instead of being sent again. Use `idempotency_key` on portfolio transactions to resend one safely.
- Defaults: `retries=3`, `backoff_factor=0.5` (0.5s, 1s, 2s).
- Invalid symbols, authentication failures, and plan-access errors are **not retryable**.

```python
from sahmk import SahmkClient

client = SahmkClient("your_api_key", retries=3, backoff_factor=0.5)
```

## Plan Behavior

Some methods are plan-gated (for example `quotes`, `historical`, `financials`, `dividends`, `events`).
When your plan does not include an endpoint, the API returns an error response (not retried automatically).

Historical data availability is plan-based:

- Free: no historical access
- Starter: `1d`, `1w`, `1mo`
- Pro: Starter intervals + `15min`, `30min`, `60min`, each up to 90 days
- Business: Pro intervals + `5min` (up to 90 days); `15min` and `30min` up to 6 months; `60min` up to 1 year
- Enterprise: custom interval access, including `1min` where enabled, by agreement

Legacy aliases `30m`, `60m`, and `1m` are still accepted. `1m` means one **month**
(`1mo`), not one minute; use `1min` for one-minute bars. Use `limit` (default 500,
max 2000) and `offset` to page through long intraday ranges.

Out-of-plan interval/range requests are returned by the API as `403 PLAN_LIMIT`.
The SDK does not hard-block these requests client-side; it passes the API response through.

## CLI Quick Start

```bash
export SAHMK_API_KEY="your_api_key"
sahmk quote 2222
sahmk market summary --index NOMU
sahmk market gainers --limit 5 --index NOMUC
sahmk historical 2222 --from 2026-01-01 --to 2026-01-28
sahmk historical 2222 --from 2026-01-01 --to 2026-01-03 --interval 60min
sahmk historical 2222 --from 2026-11-20 --to 2026-11-24 --interval 5min --limit 2000
sahmk company 2222
sahmk financials 2222
sahmk ratios 2222 --history latest --period annual --metrics core
sahmk compare 2222,1120 --metrics extended
sahmk dividends 2222
sahmk events --symbol 2222 --limit 5
sahmk depth 2222 --levels 5
sahmk trades 2222 --limit 20
sahmk trades 2222 --date 2026-11-22 --limit 200
sahmk stream 2222,1120
sahmk stream-depth 2222,1120 --levels 5
sahmk stream-trades 2222,1120
```

You can also pass the key directly:

```bash
sahmk quote 2222 --api-key your_api_key
```

## Typed Responses

Most methods return typed objects with IDE autocomplete while preserving dict-style access.
Analytics methods (`ratios`, `compare`) return raw API dict responses to match the
production contract exactly.

```python
quote = client.quote("2222")
print(quote.price)
print(quote.liquidity.net_value)

# Backwards-compatible dict access
print(quote["price"])
print(quote.get("volume"))
print(quote.raw)
```

## Financials & Analytics

```python
client.financials("1120", history="3y", result="latest")
client.ratios("1120")
client.ratios("1120", history="5y", period="quarterly", metrics="extended")
client.compare(["1120", "1180", "1010"])
client.compare(["1120", "1180", "1010", "2222"], metrics="extended")
```

Financials responses no longer include `meta`. Existing financial statement sections
(`income_statements`, `balance_sheets`, `cash_flows`) are unchanged.

Analytics `meta` remains minimal and includes only:

- `period`
- `metrics`
- `warnings`

## Market Index Scoping

Supported values:

- `TASI`
- `NOMU`
- `NOMUC` alias (normalized to `NOMU`)

```python
summary = client.market_summary(index="NOMUC")
print(summary.index)       # NOMU
print(summary.is_delayed)  # True/False by entitlement
```

## API Reference

Base URL: `https://api.sahmk.sa/api/v1`

| Endpoint | Plan | Description |
|----------|------|-------------|
| `GET /quote/{symbol}/` | Free | Stock quote |
| `GET /quotes/?symbols=...` | Starter+ | Batch quotes (up to 50) |
| `GET /historical/{symbol}/` | Starter+ | Historical and intraday OHLCV (`1min` … `1mo`, `limit`/`offset`, plan-limited) |
| `GET /market/summary/` | Free | Market overview |
| `GET /market/gainers/` | Free | Top gainers |
| `GET /market/losers/` | Free | Top losers |
| `GET /market/volume/` | Free | Volume leaders |
| `GET /market/value/` | Free | Value leaders |
| `GET /market/sectors/` | Free | Sector performance |
| `GET /market/depth/{symbol}/` | Entitled | Market depth / order book (`levels` 1-20). [Request access](https://www.sahmk.sa/developers/dashboard/realtime-access) |
| `GET /market/trades/{symbol}/` | Pro+ | Live trade prints (`limit` 1-200; `date`/`after_seq`/`cursor` session recovery) |
| `GET /companies/` | Free | Company directory and symbol discovery |
| `GET /company/{symbol}/` | Free+ | Company info (tiered by plan) |
| `GET /financials/{symbol}/` | Starter+ | Financial statements |
| `GET /analytics/ratios/{symbol}/` | Starter+ | Analytics ratios for one company |
| `GET /analytics/compare/` | Starter+ | Analytics comparison across companies |
| `GET /dividends/{symbol}/` | Starter+ | Dividend history and yield |
| `GET /events/` | Pro+ | AI-generated stock events |
| `GET, POST /portfolios/` | Free+ | List or create portfolios |
| `GET, PATCH, DELETE /portfolios/{id}/` | Free+ | Read, edit, or delete one portfolio |
| `GET, POST /portfolios/{id}/transactions/` | Free+ | Ledger, or append one transaction or a batch |
| `POST /portfolios/{id}/transactions/{tx}/reverse/` | Free+ | Reverse the latest transaction |
| `POST /portfolios/{id}/holdings/set/` | Free+ | Reconcile holdings (dry run, then apply) |
| `GET /portfolios/{id}/holdings/summary/` | Free+ | Cash, holdings, and P&L |
| `GET /portfolios/{id}/performance/` | Free+ | Daily equity series |

All endpoints require `X-API-Key`.

Full docs: [sahmk.sa/developers/docs](https://sahmk.sa/developers/docs)

## Examples

Example scripts:

- [quote.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/quote.py)
- [batch_quotes.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/batch_quotes.py)
- [historical.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/historical.py)
- [market_summary.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/market_summary.py)
- [depth.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/depth.py)
- [trades.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/trades.py)
- [analytics.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/analytics.py)
- [websocket_stream.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/websocket_stream.py)
- [websocket_depth.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/websocket_depth.py)
- [websocket_trades.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/websocket_trades.py)

## Market Depth

Market depth REST and WebSocket access are entitlement-gated. Request access from the
[developer realtime-access dashboard](https://www.sahmk.sa/developers/dashboard/realtime-access).

```python
depth = client.depth("2222", levels=5)
print(depth.best_bid, depth.best_ask, depth.spread)
for level in depth.bids:
    print(level.level, level.price, level.quantity)
```

CLI:

```bash
sahmk depth 2222 --levels 5
sahmk stream-depth 2222,1120 --levels 5
```

## Live Trades (Pro+)

Recent trade prints (REST) and a real-time tape (WebSocket). Same Pro+ plan bar as
Best Price–style realtime — no separate trades product request.

```python
trades = client.trades("2222", limit=20)
print(trades.count, trades.summary.trade_value)
for event in trades.events:
    print(event.event_time, event.price, event.quantity, event.side or "-")
```

`event.side` is optional and may be `"buy"`, `"sell"`, or `None` depending on backend availability.
Each print also carries `event.trade_seq`. The symbol, the Asia/Riyadh day of
`event_time`, and `trade_seq` together identify a print.

### Recovering a session

Pass `date` to read one Asia/Riyadh session from the recent tape (about three days)
in receive order. Dated calls return `trades.page`; follow `page.next_cursor` while
`page.has_more` is true, or let `iter_trades` do it:

```python
seen = {}
for event in client.iter_trades("2222", "2026-11-22"):
    seen[event.trade_seq] = event  # the tape can repeat a print; keep the later copy
```

`after_seq` returns only prints with a greater `trade_seq`. It requires `date` and is
a filter, not a cursor. This is the recent tape, not official session volume
(`page.complete_official_volume` is false).

CLI:

```bash
sahmk trades 2222 --limit 20
sahmk trades 2222 --date 2026-11-22 --after-seq 204505
sahmk stream-trades 2222,1120
```

## Portfolios

Portfolio methods return the API's JSON as plain dicts. Every plan can use them;
limits are Free 1 portfolio and 30 performance days, Starter 3 and 365, Pro 10 and
1095, Business 50 with no day cap, Enterprise by agreement.

```python
pf = client.create_portfolio("Core")
client.create_portfolio_transaction(pf["id"], "deposit", 10000, idempotency_key="dep-1")
client.create_portfolio_transaction(
    pf["id"], "buy", 2660, symbol="2222", quantity=100, unit_price_sar=26.6,
    idempotency_key="buy-2222-1",
)
print(client.portfolio_summary(pf["id"]))
print(client.portfolio_performance(pf["id"], days=30))

# Reconcile to target holdings: dry run first, then apply with the plan token.
target = [{"symbol": "2222", "quantity": 150, "avg_cost_sar": 26.4}]
preview = client.set_portfolio_holdings(pf["id"], target, scope="partial", cash_policy="auto_fund")
client.set_portfolio_holdings(
    pf["id"], target, scope="partial", cash_policy="auto_fund",
    dry_run=False, plan_token=preview["plan"]["plan_token"],
)
```

The ledger is append-only by `executed_at`; a backdated entry is rejected. Only the
latest transaction can be reversed (`reverse_portfolio_transaction`). For an atomic
batch, use `create_portfolio_transactions(portfolio_id, transactions, batch_idempotency_key)`.

## WebSocket Streaming (Pro+)

```python
import asyncio
from sahmk import SahmkClient

client = SahmkClient("your_api_key")

async def on_quote(msg):
    print(f"{msg['symbol']}: {msg['data']['price']}")

asyncio.run(client.stream(["2222", "1120"], on_quote=on_quote))
```

Depth streaming uses a dedicated channel:

```python
async def on_depth(msg):
    print(f"{msg['symbol']}: {msg['best_bid']} / {msg['best_ask']}")

asyncio.run(client.stream_depth(["2222"], on_depth=on_depth, levels=5))
```

Trades streaming also uses a dedicated channel:

```python
async def on_trade(msg):
    print(f"{msg['symbol']}: {msg['price']} x {msg['quantity']} side={msg.get('side') or '-'}")

async def on_snapshot(msg):
    print(f"snapshot {msg['symbol']}: {msg['count']} events")

asyncio.run(
    client.stream_trades(["2222"], on_trade=on_trade, on_snapshot=on_snapshot)
)
```

The streaming client auto-reconnects with exponential backoff + jitter and
resubscribes symbols after reconnect.

Runtime behavior (verified with backend contract):

- Authentication close code: `4401` (non-retryable)
- Entitlement / plan / inactive / unverified close code: `4403` (non-retryable)
- Invalid JSON / unknown action returns `type="error"` while socket stays open
- Active subscriptions are per-connection; the SDK automatically resubscribes after reconnect
- Symbol chunking uses backend `connected.limits.max_symbols_per_call` when available

For a production-style long-running process (logging, graceful shutdown, reconnect
visibility, and automatic resubscribe behavior), see:

- [examples/websocket_stream.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/websocket_stream.py)

Changelog: [CHANGELOG.md](https://github.com/sahmk-sa/sahmk-python/blob/main/CHANGELOG.md)  
Roadmap: [ROADMAP.md](https://github.com/sahmk-sa/sahmk-python/blob/main/ROADMAP.md)

## License

MIT — see [LICENSE](https://github.com/sahmk-sa/sahmk-python/blob/main/LICENSE)
