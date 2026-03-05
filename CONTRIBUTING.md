# Contributing to MCP Server for MetaTrader 5

Thank you for your interest in contributing! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior by opening an issue.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a branch for your changes
4. Make your changes and test them
5. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- MetaTrader 5 terminal installed (Windows only)
- An MT5 demo account for testing

### Install Dependencies

```bash
# Clone your fork
git clone https://github.com/<your-username>/mt5-mcp.git
cd mt5-mcp

# Install with dev dependencies
uv sync --extra dev
```

### Running Tests

```bash
# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_server.py
```

### Running the Server Locally

```bash
# Copy environment template
cp .env.example .env
# Edit .env with your MT5 demo credentials

# Run the server
uv run mcp-server-mt5
```

## How to Contribute

### Reporting Bugs

- Use the [Bug Report](https://github.com/P7AC1D/mt5-mcp/issues/new?template=bug_report.md) issue template
- Include your Python version, MT5 terminal version, and OS version
- Provide steps to reproduce the issue
- Include relevant log output

### Suggesting Features

- Use the [Feature Request](https://github.com/P7AC1D/mt5-mcp/issues/new?template=feature_request.md) issue template
- Describe the use case and expected behavior
- Explain why this would be useful to other users

### Submitting Code

1. **Create an issue first** for significant changes to discuss the approach
2. **Branch from `main`** — use descriptive branch names:
   - `feature/add-trailing-stop` for new features
   - `fix/order-timeout-handling` for bug fixes
   - `docs/update-api-reference` for documentation
3. **Write tests** for new functionality
4. **Follow existing code style** (see [Coding Standards](#coding-standards))
5. **Keep commits focused** — one logical change per commit

## Pull Request Process

1. **Update documentation** if your change affects user-facing behavior
2. **Add or update tests** to cover your changes
3. **Ensure all tests pass** before submitting
4. **Fill out the PR template** completely
5. **Link related issues** using `Closes #123` in the PR description

### PR Review Criteria

- Code follows the project's style and conventions
- Tests are included and passing
- Documentation is updated where necessary
- No secrets, credentials, or personal data are included
- Changes are focused and minimal (no unrelated modifications)

### Merge Policy

- PRs require at least one approving review
- All CI checks must pass
- Squash merging is preferred for clean history
- The PR author should not merge their own PR

## Coding Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions
- Use type hints for function parameters and return values
- Use descriptive variable and function names
- Keep functions focused and concise

### Project Conventions

- **Configuration**: Use environment variables via `pydantic-settings`, never hardcode credentials
- **Secrets**: Use `SecretStr` from Pydantic for sensitive values
- **Error handling**: Use MT5 error codes and provide meaningful error messages
- **Tool annotations**: Mark destructive tools (e.g., `send_order`) with `destructiveHint=True`
- **Logging**: Use the `logging` module, not `print()` statements

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add trailing stop support for positions
fix: handle timeout when MT5 terminal is not responding
docs: update installation instructions for Linux via Wine
test: add unit tests for order validation
```

## Security

- **Never commit credentials** — use `.env` files (already in `.gitignore`)
- **Review `.env.example`** if you add new config options — use placeholder values only
- Report security vulnerabilities privately (see [SECURITY.md](SECURITY.md))

## Questions?

Open a [discussion](https://github.com/P7AC1D/mt5-mcp/discussions) or issue if you have questions about contributing.

Thank you for helping make this project better!
