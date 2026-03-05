# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

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

- **STDIO transport** (default): Communication stays local to your machine — no network exposure
- **HTTP transport**: When using `--transport http`, the server listens on the network
  - Bind to `127.0.0.1` instead of `0.0.0.0` for local-only access
  - Use firewall rules to restrict access when binding to all interfaces
  - Consider placing behind a reverse proxy with TLS for production use
  - The HTTP transport does not include authentication — secure the network layer

### Trading Safety

- Always test with a **demo account** before using real funds
- The `send_order` tool is annotated with `destructiveHint=True` to prompt confirmation
- Review all trade parameters before confirming execution
- Consider implementing additional safeguards (position limits, daily loss limits) for automated use

## Dependency Security

This project uses:
- `pydantic` / `pydantic-settings` for validated configuration with secret handling
- `mcp` SDK for the Model Context Protocol
- `MetaTrader5` official Python package

Keep dependencies updated to receive security patches:
```bash
uv sync --upgrade
```
