# SAHMK Python SDK

A lightweight Python client for the [SAHMK Developer API](https://sahmk.sa/developers) — real-time and historical Saudi stock market (Tadawul) data.

## Features

- **Real-time quotes** — live prices for 350+ Tadawul stocks
- **Batch quotes** — up to 50 stocks in a single request
- **Historical data** — daily/weekly/monthly OHLCV with custom date ranges
- **Market overview** — TASI index, gainers, losers, volume/value leaders, sectors
- **Company info** — fundamentals, technicals, valuation, analyst consensus (by plan)
- **Financials** — income statements, balance sheets, cash flow
- **Dividends** — history, yield, upcoming payments
- **Events** — AI-generated stock event summaries
- **WebSocket streaming** — real-time price updates pushed to you (Pro+ plan)

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
print(f"{quote['name_en']}: {quote['price']} SAR ({quote['change_percent']}%)")

# Get market summary
market = client.market_summary()
print(f"TASI: {market['index_value']} ({market['index_change_percent']}%)")

# Batch quotes (Starter+ plan)
result = client.quotes(["2222", "1120", "4191"])
for q in result["quotes"]:
    print(f"{q['symbol']}: {q['price']}")
```

## Get Your API Key

1. Sign up at [sahmk.sa/developers](https://sahmk.sa/developers)
2. Verify your email
3. Go to Dashboard → API Keys → Create Key
4. Copy your key (starts with `shmk_live_` or `shmk_test_`)

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
| [`websocket_stream.py`](examples/websocket_stream.py) | Real-time WebSocket streaming (Pro+) |

## API Reference

Base URL: `https://app.sahmk.sa/api/v1`

| Endpoint | Plan | Description |
|----------|------|-------------|
| `GET /quote/{symbol}/` | Free | Stock quote |
| `GET /quotes/?symbols=...` | Starter+ | Batch quotes (up to 50) |
| `GET /historical/{symbol}/` | Starter+ | Historical OHLCV data |
| `GET /market/summary/` | Free | Market overview & TASI index |
| `GET /market/gainers/` | Free | Top gainers |
| `GET /market/losers/` | Free | Top losers |
| `GET /market/volume/` | Free | Volume leaders |
| `GET /market/value/` | Free | Value leaders |
| `GET /market/sectors/` | Free | Sector performance |
| `GET /company/{symbol}/` | Free+ | Company info (tiered by plan) |
| `GET /financials/{symbol}/` | Starter+ | Financial statements |
| `GET /dividends/{symbol}/` | Starter+ | Dividend history & yield |
| `GET /events/` | Pro+ | AI-generated stock events |

All endpoints require the `X-API-Key` header.

Full docs: [sahmk.sa/developers/docs](https://sahmk.sa/developers/docs)

## WebSocket Streaming (Pro+)

```python
import asyncio
from sahmk import SahmkClient

client = SahmkClient("your_api_key")

async def on_quote(msg):
    symbol = msg["symbol"]
    price = msg["data"]["price"]
    print(f"{symbol}: {price}")

asyncio.run(client.stream(["2222", "1120"], on_quote=on_quote))
```

Connection URL: `wss://app.sahmk.sa/ws/v1/stocks/?api_key=YOUR_KEY`

## License

MIT — see [LICENSE](LICENSE)
