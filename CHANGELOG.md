# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
