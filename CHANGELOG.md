# Changelog

All notable changes to the `sahmk` Python SDK will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/).

## [0.9.3] — 2026-05-03

### Changed

- docs: clarify official distribution channels (GitHub + PyPI only)

## [0.9.2] — 2026-04-30

### Changed

- Align docs/examples/tests with current API contract:
  - `financials` responses do not include `meta`
  - analytics `meta` remains minimal (`period`, `metrics`, `warnings`)

## [0.9.1] — 2026-04-30

### Fixed

- Fix analytics endpoint paths to match production API.
- `ratios()` now calls `GET /analytics/ratios/{symbol}/`
- `compare()` now calls `GET /analytics/compare/`
- Analytics SDK methods now return the production response shape as-is:
  - ratios: `symbol`, `ratios`, `meta`
  - compare: `results`, `count`, `meta`

## [0.9.0] — 2026-04-30

### Added

- Add analytics ratios and compare endpoints; enhance financials query params.
- New `ratios(symbol, history="latest", period="annual", metrics="core")` client method
- New `compare(symbols, metrics="core")` client method with support for symbol lists and comma-separated symbol strings
- New typed analytics models: `RatioRow`, `RatiosResponse`, `CompareRow`, and `CompareResponse`

### Changed

- `financials()` now accepts optional query kwargs: `type`, `period`, `statement_period`, `history`, `metrics`, `result`, `include_quality`, and `include_partial`
- When both `period` and `statement_period` are provided to `financials()`, `period` takes precedence
- README now includes financials analytics examples for `financials`, `ratios`, and `compare`

## [0.8.0] — 2026-04-24

### Added

- New `companies()` SDK method for canonical symbol discovery via `GET /companies/`, with support for `search`, `market`, `limit`, and `offset`
- Discovery-first README guidance and examples for symbol/name search, market filtering, and offset-based pagination before calling `quote()`/`company()`
- Integration coverage for live company directory response shape

### Changed

- Company directory market filter now uses the same normalization rules as market endpoints (`TASI`/`NOMU`, `NOMUC` alias to `NOMU`)
- API reference docs now include `GET /companies/` as the symbol discovery endpoint

### Fixed

- Client-side pagination validation for company discovery now enforces `limit > 0` and `offset >= 0` before request dispatch

## [0.7.0] — 2026-04-18

### Added

- Identifier-resolution support for quote endpoints in the SDK: `quote()` and `quotes()` now accept symbols, Arabic names, English names, and aliases when backend resolution is enabled
- New typed resolution metadata: `IdentifierResolution`, `Quote.requested_identifier`, `Quote.resolved_symbol`, `Quote.resolution`, plus batch-level `resolved`, `ambiguous`, and `unknown`
- New resolution-focused exceptions: `SahmkIdentifierResolutionError`, `SahmkAmbiguousIdentifierError`, and `SahmkUnknownIdentifierError`

### Changed

- `quotes()` now prefers the new `identifiers` backend parameter and transparently falls back to legacy `symbols` for older backends
- Resolution-related exceptions now preserve backend-provided `status_code` and `error_code` semantics
- Quote docs and examples now explicitly show both classic symbol usage and identifier-based usage

### Fixed

- Improved backward compatibility during backend rollout by adding automatic quotes parameter fallback instead of requiring immediate backend parity

## [0.6.2] — 2026-04-12

### Added

- Market endpoints now accept optional `index` in SDK methods and CLI (`--index`) for `TASI`/`NOMU`, with `NOMUC` alias normalized to `NOMU`
- New `SahmkInvalidIndexError` for clear handling of invalid market index usage (`INVALID_INDEX`)
- Market typed response models now expose top-level `index` and `is_delayed` fields

### Changed

- Market method docs/examples updated to reflect index scoping and delayed-vs-realtime response metadata
- Test coverage expanded for index query propagation, alias normalization, and invalid-index failures

## [0.6.1] — 2026-04-02

### Fixed

- **CLI `--compact` flag** now works in both positions: `sahmk --compact quote 2222` and `sahmk quote 2222 --compact` (previously only the first form worked)
- **Non-JSON 200 responses** (e.g. proxy HTML errors) are now wrapped in `SahmkError` instead of raising a raw `ValueError`
- **`on_reconnect` docstring** corrected — it fires before a reconnect attempt (after backoff delay), not after a successful reconnection
- **Test fixtures** aligned with real API response shapes (market summary, company, financials, dividends, events)
- **`quotes([])` guard** — calling `quotes()` with an empty list now raises `ValueError` immediately instead of sending an invalid request
- **Redundant 429** removed from internal `_RETRIABLE_STATUS_CODES` (429 is handled by its own dedicated branch)

### Changed

- **PyPI classifier** updated from "3 - Alpha" to "4 - Beta"

## [0.6.0] — 2026-04-02

### Added

- **CLI: `company` command** — `sahmk company 2222` to get company info
- **CLI: `financials` command** — `sahmk financials 2222` for financial statements
- **CLI: `dividends` command** — `sahmk dividends 2222` for dividend history
- **CLI: `events` command** — `sahmk events --symbol 2222 --limit 10` for stock events
- **CLI: `stream` command** — `sahmk stream 2222,1120` for real-time WebSocket streaming with auto-reconnect; outputs JSON lines to stdout, status/errors to stderr; stop with Ctrl+C

### Changed

- CLI now covers all SDK endpoints (previously only quote, quotes, market, historical)
- Stream command outputs each quote as a single JSON line for easy piping/parsing

## [0.5.0] — 2026-04-02

### Added

- **Typed response models** — all client methods now return typed dataclass objects (e.g., `Quote`, `Company`, `HistoricalResponse`, `FinancialsResponse`, `DividendsResponse`, `EventsResponse`, `MarketSummary`, etc.) with IDE autocompletion and attribute access
- **Full backwards compatibility** — all typed models support dict-style `[]` access, `.get()`, `.keys()`, `.values()`, `.items()`, and `in` checks; existing code using `result["price"]` continues to work unchanged
- **`.raw` attribute** — every model exposes the original API response dict via `.raw` for cases where you need the full untyped data
- **Nested typed models** — complex responses have properly typed sub-objects (e.g., `Quote.liquidity` returns a `Liquidity` object, `Company.fundamentals` returns a `Fundamentals` object)
- **Plan-aware models** — `Company` model gracefully handles tiered responses (Free: basic fields, Starter: +fundamentals, Pro: +technicals/valuation/analysts) with `None` for unavailable sections

### Changed

- All client methods (`quote()`, `quotes()`, `historical()`, `market_summary()`, `gainers()`, `losers()`, `volume_leaders()`, `value_leaders()`, `sectors()`, `company()`, `financials()`, `dividends()`, `events()`) now return typed model instances instead of plain dicts
- CLI `_print_json()` now handles model objects by serializing their `.raw` dict

## [0.4.0] — 2026-04-02

### Added

- **Automatic retries** for transient failures — 429 (rate limit) and 5xx (server errors) are retried with exponential backoff (default: 3 attempts, delays of 0.5s → 1s → 2s)
- **`Retry-After` header support** — 429 responses with a `Retry-After` header use the server-specified wait time instead of computed backoff
- **`SahmkRateLimitError`** — new exception subclass of `SahmkError` with rate-limit metadata: `retry_after`, `rate_limit`, `rate_remaining`, `rate_reset` (from API response headers)
- **Configurable retry behavior** — `SahmkClient(retries=3, backoff_factor=0.5, retry_on_timeout=True)` with sensible defaults
- **Timeout retry support** — request timeouts can optionally be retried (enabled by default)

### Changed

- `SahmkClient.__init__()` now accepts `retries`, `backoff_factor`, and `retry_on_timeout` keyword arguments (all optional, backwards-compatible)
- 4xx client errors (400, 401, 403, 404) are never retried — only 429 and 5xx trigger retry logic
- Network errors (`ConnectionError`, etc.) are raised immediately and never retried (only timeouts are retried when `retry_on_timeout=True`)

### Fixed

- Rate limit errors now provide structured metadata instead of a generic message

## [0.3.0] — 2026-04-02

### Added

- **WebSocket auto-reconnect** — the streaming client now automatically reconnects on disconnect with exponential backoff (1s → 2s → 4s … capped at 60s by default)
- **Automatic resubscription** — all symbols are resubscribed after a successful reconnect, no developer action needed
- **`on_disconnect` callback** — optional async callback that fires when the connection drops, receives a reason string
- **`on_reconnect` callback** — optional async callback that fires before a reconnect attempt, receives the attempt number
- **Configurable reconnect behavior** — `max_reconnect_attempts` (0 = unlimited, -1 = disabled), `initial_reconnect_delay`, `max_reconnect_delay`
- **Error surfacing** — WebSocket errors are now logged via `logging` when no `on_error` callback is provided, preventing silent failures
- **`SahmkError` re-exported** from `sahmk` package for convenience (`from sahmk import SahmkError`)
- This `CHANGELOG.md` file

### Changed

- WebSocket `stream()` method now accepts additional keyword arguments for reconnect configuration; all new parameters are optional and backwards-compatible
- Auth errors (`SahmkError`) during streaming are raised immediately and never retried
- Internal streaming logic refactored into `_stream_connection()` for cleaner separation of connection lifecycle and reconnect orchestration

### Fixed

- WebSocket errors received during streaming are no longer silently dropped when no `on_error` callback is provided — they are now logged as warnings

## [0.2.1] — 2026-03-01

### Fixed

- Minor packaging and metadata improvements

## [0.2.0] — 2026-02-15

### Added

- CLI command: `sahmk`
- CLI subcommands: `quote`, `quotes`, `market`, `historical`
- API key support via `--api-key` flag or `SAHMK_API_KEY` environment variable
- `--compact` flag for compact JSON output

## [0.1.0] — 2026-01-20

### Added

- Core REST client for all SAHMK API endpoints (quotes, market, company, historical, financials, dividends, events)
- WebSocket streaming support (Pro+ plan)
- PyPI package publishing
- MIT license
