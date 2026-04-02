# SAHMK Python SDK Roadmap

This roadmap outlines the planned direction for the `sahmk` Python SDK.
Timelines are approximate and can change based on user feedback and API evolution.

## Principles

- Keep onboarding fast: install and first successful call in under a minute.
- Keep SDK surface clear: one obvious method per endpoint/use case.
- Improve reliability in steps without overcomplicating the initial developer experience.

## Current Status

### v0.1.0 (released)

- Core REST endpoints for quotes, market, company, historical, financials, dividends, and events
- WebSocket streaming support
- PyPI publishing setup

### v0.2.0 (released)

- CLI command: `sahmk`
- CLI commands for `quote`, `quotes`, `market`, and `historical`
- API key support via `--api-key` or `SAHMK_API_KEY`

### v0.3.0 (released)

- WebSocket auto-reconnect with exponential backoff
- Automatic resubscribe after reconnect
- `on_disconnect` and `on_reconnect` callbacks for connection lifecycle visibility
- Configurable reconnect behavior (`max_reconnect_attempts`, delays)
- Error surfacing — no more silent failures in streaming
- `SahmkError` exported from package root

### v0.4.0 (released)

- Automatic retries with exponential backoff for 429 and 5xx
- `Retry-After` header support for rate-limited responses
- `SahmkRateLimitError` with rate-limit metadata
- Configurable retry behavior (`retries`, `backoff_factor`, `retry_on_timeout`)
- Timeout retries (opt-in, enabled by default)

## Next Milestones

### v0.5.0 (planned) — Typed response models

- Typed response models for key endpoints (quote, company, historical, etc.)
- Improved developer experience with IDE autocompletion
- Backwards-compatible — raw dict access preserved

### v0.6.0 (planned) — CLI expansion

- CLI commands for `company`, `financials`, `dividends`, `events`
- Optional `stream` CLI command
- Improved CLI output modes

## Documentation and Examples Plan

- Keep README focused on 10-second success
- Add practical examples (batch quotes, historical scans, simple watchlist scripts)
- Add a troubleshooting section for common errors (invalid key, plan limits, rate limits)

## Public vs Private Roadmap

Recommended approach:

- Keep this high-level roadmap **public** to build trust and set expectations.
- Keep internal details **private** (exact launch dates, infrastructure, commercial terms, security specifics, unreleased enterprise commitments).

This file is intended to stay public and product-focused.
