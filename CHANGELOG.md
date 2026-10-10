# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Unreleased

- Upgrade to official MCP SDK 2.3.0 and current Streamable HTTP `/mcp`.
- Preserve opt-in legacy SSE for existing clients and all 33 tool names/success text payloads.
- Serialize whole MT5 operations on a bounded owner with cancellation-safe lifecycle, account identity/generation checks and a durable mutation journal.
- Return real MCP errors/structured output, fix resource template discovery and distinguish native failures from empty results.
- Add input/result limits, UTC dates, loopback/auth defaults, Host/Origin checks, runtime locking and readiness probes.
- Pin reproducible dependencies; add Windows-only dependency markers, concurrent protocol/safety tests, Linux/Windows CI, and versioned Windows logon-task deployment with rollback.
- Migration details and limitations: [modernization](docs/modernization.md).

## [Unreleased]

## [0.1.0] - 2025-01-01

### Added

- Initial release of MCP Server for MetaTrader 5
- STDIO and HTTP transport support
- Market data tools: symbols, ticks, OHLC bars, tick ranges
- Account information tool
- Position and order management tools
- Trade execution with safety annotations (`destructiveHint`)
- Historical data access (orders and deals)
- MCP resource endpoints for passive polling
- Configuration via environment variables with `pydantic-settings`
- Secure credential handling with `SecretStr`
