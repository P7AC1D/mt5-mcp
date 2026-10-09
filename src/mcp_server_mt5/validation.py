"""Input validation shared by MCP dispatch and date-based handlers."""

import math
from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator

from .config import MT5Settings


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Preserve accepted naive inputs, but interpret them consistently as UTC.
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def validate_arguments(schema: dict, arguments: dict[str, Any], settings: MT5Settings) -> None:
    errors = list(Draft202012Validator(schema).iter_errors(arguments))
    if errors:
        # Do not echo submitted values: they may contain a password.
        error = errors[0]
        path = ".".join(str(x) for x in error.absolute_path) or "arguments"
        raise ValueError(f"Invalid {path}: failed {error.validator} validation")
    for key, value in arguments.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{key} must be finite")
        if (
            key in {"count", "volume", "ticket", "order_id", "position", "order", "login"}
            and isinstance(value, (int, float))
            and value <= 0
        ):
            raise ValueError(f"{key} must be positive")
        if (
            key in {"start_pos", "deviation", "sl", "tp", "price", "price_open", "price_close"}
            and isinstance(value, (int, float))
            and value < 0
        ):
            raise ValueError(f"{key} cannot be negative")
        if isinstance(value, str) and len(value) > (4096 if key == "password" else 512):
            raise ValueError(f"{key} is too long")
    if arguments.get("count", 0) > settings.max_rows:
        raise ValueError(f"count exceeds configured limit ({settings.max_rows})")
    dates = {
        key: parse_utc(arguments[key])
        for key in ("date_from", "date_to", "expiration")
        if key in arguments
    }
    if "date_from" in dates and "date_to" in dates:
        days = (dates["date_to"] - dates["date_from"]).total_seconds() / 86400
        if days < 0 or days > settings.max_range_days:
            raise ValueError(
                f"Date range must be ordered and at most {settings.max_range_days} days"
            )
