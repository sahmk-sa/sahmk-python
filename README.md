# SAHMK Python SDK

Official Python SDK for [Sahmk](https://sahmk.sa/developers) — Saudi market data and richer market workflows for developers.

Use one client for live Tadawul quotes, market-level insights, company/fundamental data, financials, events, and historical series.

## Features

- **Real-time quotes** for 350+ Tadawul stocks
- **Batch quotes** for up to 50 symbols per request
- **Historical OHLCV** data with date-range support
- **Market overview** with index scoping (`TASI`/`NOMU`)
- **Company directory** endpoint for symbol discovery
- **Company/fundamental** data (plan-dependent fields)
- **Financials, dividends, and events** endpoints (by plan)
- **WebSocket streaming** for real-time updates (Pro+)

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

- The client retries transient failures: **HTTP 429** and **5xx** errors.
- Defaults: `retries=3`, `backoff_factor=0.5` (0.5s, 1s, 2s).
- Invalid symbols, authentication failures, and plan-access errors are **not retryable**.

```python
from sahmk import SahmkClient

client = SahmkClient("your_api_key", retries=3, backoff_factor=0.5)
```

## Plan Behavior

Some methods are plan-gated (for example `quotes`, `historical`, `financials`, `dividends`, `events`).
When your plan does not include an endpoint, the API returns an error response (not retried automatically).

## CLI Quick Start

```bash
export SAHMK_API_KEY="your_api_key"
sahmk quote 2222
sahmk market summary --index NOMU
sahmk market gainers --limit 5 --index NOMUC
sahmk historical 2222 --from 2026-01-01 --to 2026-01-28
sahmk company 2222
sahmk financials 2222
sahmk dividends 2222
sahmk events --symbol 2222 --limit 5
sahmk stream 2222,1120
```

You can also pass the key directly:

```bash
sahmk quote 2222 --api-key your_api_key
```

## Typed Responses

All methods return typed objects with IDE autocomplete while preserving dict-style access.

```python
quote = client.quote("2222")
print(quote.price)
print(quote.liquidity.net_value)

# Backwards-compatible dict access
print(quote["price"])
print(quote.get("volume"))
print(quote.raw)
```

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

Base URL: `https://app.sahmk.sa/api/v1`

| Endpoint | Plan | Description |
|----------|------|-------------|
| `GET /quote/{symbol}/` | Free | Stock quote |
| `GET /quotes/?symbols=...` | Starter+ | Batch quotes (up to 50) |
| `GET /historical/{symbol}/` | Starter+ | Historical OHLCV data |
| `GET /market/summary/` | Free | Market overview |
| `GET /market/gainers/` | Free | Top gainers |
| `GET /market/losers/` | Free | Top losers |
| `GET /market/volume/` | Free | Volume leaders |
| `GET /market/value/` | Free | Value leaders |
| `GET /market/sectors/` | Free | Sector performance |
| `GET /companies/` | Free | Company directory and symbol discovery |
| `GET /company/{symbol}/` | Free+ | Company info (tiered by plan) |
| `GET /financials/{symbol}/` | Starter+ | Financial statements |
| `GET /dividends/{symbol}/` | Starter+ | Dividend history and yield |
| `GET /events/` | Pro+ | AI-generated stock events |

All endpoints require `X-API-Key`.

Full docs: [sahmk.sa/developers/docs](https://sahmk.sa/developers/docs)

## Examples

Example scripts:

- [quote.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/quote.py)
- [batch_quotes.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/batch_quotes.py)
- [historical.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/historical.py)
- [market_summary.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/market_summary.py)
- [websocket_stream.py](https://github.com/sahmk-sa/sahmk-python/blob/main/examples/websocket_stream.py)

## WebSocket Streaming (Pro+)

```python
import asyncio
from sahmk import SahmkClient

client = SahmkClient("your_api_key")

async def on_quote(msg):
    print(f"{msg['symbol']}: {msg['data']['price']}")

asyncio.run(client.stream(["2222", "1120"], on_quote=on_quote))
```

The streaming client auto-reconnects with exponential backoff and resubscribes symbols.

Changelog: [CHANGELOG.md](https://github.com/sahmk-sa/sahmk-python/blob/main/CHANGELOG.md)  
Roadmap: [ROADMAP.md](https://github.com/sahmk-sa/sahmk-python/blob/main/ROADMAP.md)

## License

MIT — see [LICENSE](https://github.com/sahmk-sa/sahmk-python/blob/main/LICENSE)
