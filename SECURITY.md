# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in this project, please report it responsibly:

1. **GitHub Private Vulnerability Reporting**: Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) feature on this repository.
2. **Email**: If private reporting is not available, contact the maintainers directly via the email listed in their GitHub profile.

### What to Include

- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Suggested fix (if any)

### Response Timeline

- **Acknowledgement**: Within 48 hours of report
- **Initial assessment**: Within 1 week
- **Fix or mitigation**: Dependent on severity, targeting within 30 days for critical issues

## Security Considerations for Users

### Credential Management

- **Never commit** your `.env` file or MT5 credentials to version control
- Use the `.env.example` template with placeholder values as a reference
- Credentials are handled via `pydantic-settings` with `SecretStr` to prevent accidental logging
- Rotate your MT5 password if you suspect it has been exposed

### Network Security

- STDIO uses local process streams. HTTP binds to loopback by default.
- Non-loopback HTTP requires an explicitly provisioned bearer token and allowed
  Host names. Configure Origin allowlists; do not disable DNS-rebinding protection.
- Use TLS on remote links. Shared bearer-token mode is intended for preconfigured
  private clients, not a claim of implementing MCP OAuth. Use an OAuth gateway
  when the client requires OAuth discovery/authorization.
- `/healthz` exposes only liveness/version; other endpoints require a token when
  one is configured. No automatic CORS wildcard or firewall opening is provided.
- Legacy SSE is opt-in and shares authentication, body limits, bounded sessions,
  and a maximum connection lifetime with the primary transport.

### Trading Safety

- `destructiveHint` and `readOnlyHint` are client hints. They are not an
  authorization mechanism or server-enforced trade confirmation.
- Each server must exclusively own one terminal/account. A process lock protects
  only processes using the same lock path; it cannot prevent a human or another
  application changing the terminal. Account checks reduce this risk but cannot
  eliminate a GUI/native race after the final check.
- Never retry a dispatched trading mutation because of timeout, cancellation,
  HTTP disconnect or an unknown outcome. Reconcile broker orders/deals first.
- Keep operation journals private: they contain trading results, though no request
  arguments or login passwords. Preserve the shared journal across upgrades.
- A native hang cannot safely be cancelled by Python. New work is rejected while
  overdue, and a shutdown timeout retains the process lock until process exit.
  Restart only after the old process is gone and uncertain outcomes are reviewed.
- Account switching is disabled by default. Prefer separate terminals/processes
  for separate accounts. The bridge does not implement per-client permissions.

## Dependency Security

This project uses:
- `pydantic` / `pydantic-settings` for validated configuration with secret handling
- `mcp` SDK for the Model Context Protocol
- `MetaTrader5` official Python package

Dependencies are committed in `uv.lock`. Review security updates deliberately,
regenerate the lock, and rerun the complete suite before deployment; normal
installs use `uv sync --locked`. Do not upgrade dependencies implicitly at startup.
