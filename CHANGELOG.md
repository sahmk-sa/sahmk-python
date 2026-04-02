# Changelog

All notable changes to the `sahmk` Python SDK will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/).

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
