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

## Next Milestones

### v0.3.0 (planned) — Streaming reliability

- Optional WebSocket auto-reconnect
- Automatic resubscribe after reconnect
- Better stream lifecycle/error messages for long-running consumers

### v0.4.0 (planned) — Rate-limit and retry helpers

- Retry strategy for transient HTTP failures (`429`/`5xx`)
- Helper utilities for reading rate-limit behavior in a friendly way
- Better guidance for backoff patterns in docs and examples

### v0.5.0 (planned) — Developer ergonomics

- Typed response models for key endpoints (where useful)
- Improved CLI output modes (compact/table)
- Better exception categories for easier app-level handling

## Documentation and Examples Plan

- Keep README focused on 10-second success
- Add practical examples (batch quotes, historical scans, simple watchlist scripts)
- Add a troubleshooting section for common errors (invalid key, plan limits, rate limits)

## Public vs Private Roadmap

Recommended approach:

- Keep this high-level roadmap **public** to build trust and set expectations.
- Keep internal details **private** (exact launch dates, infrastructure, commercial terms, security specifics, unreleased enterprise commitments).

This file is intended to stay public and product-focused.
