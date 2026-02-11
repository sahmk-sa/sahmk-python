# SAHMK Python SDK

A lightweight Python client for the [SAHMK Developer API](https://sahmk.sa/developers) — real-time and historical Saudi stock market (Tadawul) data.

## Features

- **Real-time quotes** — live prices for 200+ Tadawul stocks
- **Batch quotes** — up to 50 stocks in a single request
- **Historical data** — daily OHLCV data with custom date ranges
- **Market overview** — index, gainers, losers, volume leaders
- **Company financials** — income statements, balance sheets
- **Dividends** — historical dividend data
- **WebSocket streaming** — real-time price updates pushed to you (Pro plan)

## Installation

```bash
pip install requests websockets
```

Or clone this repo:

```bash
git clone https://github.com/sahmk-sa/sahmk-python.git
cd sahmk-python
pip install -r requirements.txt
```

## Quick Start

```python
from sahmk import SahmkClient

client = SahmkClient("your_api_key")

# Get a stock quote
quote = client.quote("2222")
print(f"{quote['name']}: {quote['last_price']} SAR ({quote['change_pct']})")

# Get market summary
market = client.market_summary()
print(f"TASI: {market['index_value']} ({market['index_change_pct']})")

# Batch quotes
quotes = client.quotes(["2222", "1120", "4191"])
for q in quotes:
    print(f"{q['symbol']}: {q['last_price']}")
```

## Get Your API Key

1. Sign up at [sahmk.sa/developers](https://sahmk.sa/developers)
2. Verify your email
3. Go to Dashboard → API Keys → Create Key
4. Copy your key (starts with `shmk_live_`)

## Plans

| Plan | Price | Requests/Day | WebSocket |
|------|-------|-------------|-----------|
| Free | 0 SAR | 100 | - |
| Starter | 149 SAR/mo | 5,000 | - |
| Pro | 499 SAR/mo | 50,000 | Yes |
| Enterprise | 1,499+ SAR/mo | Unlimited | Yes |

## Examples

Check the [`examples/`](examples/) directory:

| File | Description |
|------|-------------|
| [`quote.py`](examples/quote.py) | Get a single stock quote |
| [`batch_quotes.py`](examples/batch_quotes.py) | Fetch multiple stocks at once |
| [`historical.py`](examples/historical.py) | Historical price data |
| [`market_summary.py`](examples/market_summary.py) | Market overview and movers |
| [`websocket_stream.py`](examples/websocket_stream.py) | Real-time WebSocket streaming (Pro) |

## API Reference

Base URL: `https://app.sahmk.sa/api/v1`

| Endpoint | Description |
|----------|-------------|
| `GET /quote/{symbol}/` | Real-time stock quote |
| `GET /quotes/?symbols=...` | Batch quotes (up to 50) |
| `GET /historical/{symbol}/` | Historical OHLCV data |
| `GET /market/summary/` | Market overview |
| `GET /market/gainers/` | Top gainers |
| `GET /market/losers/` | Top losers |
| `GET /market/volume/` | Volume leaders |
| `GET /market/sectors/` | Sector performance |
| `GET /financials/{symbol}/` | Financial statements |
| `GET /company/{symbol}/` | Company info |
| `GET /dividends/{symbol}/` | Dividend history |
| `GET /events/` | Market events |

All endpoints require the `X-API-Key` header.

Full docs: [sahmk.sa/developers/docs](https://sahmk.sa/developers/docs)

## WebSocket Streaming (Pro)

```python
import asyncio
from sahmk import SahmkClient

client = SahmkClient("your_api_key")

async def on_quote(data):
    print(f"{data['symbol']}: {data['last_price']}")

asyncio.run(client.stream(["2222", "1120"], on_quote=on_quote))
```

Connection URL: `wss://app.sahmk.sa/ws/v1/stocks/?api_key=YOUR_KEY`

## License

MIT — see [LICENSE](LICENSE)
