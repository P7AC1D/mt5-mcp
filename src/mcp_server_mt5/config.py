"""Validated server and terminal settings. No secret values are logged."""

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MT5Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MT5_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    login: int | None = None
    password: SecretStr | None = None
    server: str | None = None
    path: str | None = None
    expected_login: int | None = None
    expected_server: str | None = None
    allow_account_switch: bool = False
    queue_size: int = Field(default=64, ge=1, le=4096)
    readiness_interval: float = Field(default=5, ge=0.01, le=300)
    request_timeout: float = Field(default=60, gt=0, le=600)
    shutdown_timeout: float = Field(default=65, gt=0, le=600)
    initialize_timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    max_rows: int = Field(default=100000, ge=1, le=1000000)
    max_range_days: int = Field(default=366, ge=1, le=3650)
    max_request_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    max_sessions: int = Field(default=128, ge=1, le=10000)
    session_idle_timeout: float = Field(default=300, gt=0)
    legacy_sse: bool = False
    legacy_sse_max_seconds: float = Field(default=300, gt=0)
    http_token: SecretStr | None = None
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    )
    lock_file: Path = Path(".runtime/mt5.lock")
    journal_file: Path | None = Path(".runtime/operations.jsonl")
    log_file: Path | None = None

    @property
    def has_credentials(self) -> bool:
        return self.login is not None and self.password is not None

    def get_init_kwargs(self) -> dict:
        kwargs: dict = {"timeout": self.initialize_timeout_ms}
        if self.path:
            kwargs["path"] = self.path
        if self.has_credentials and self.password is not None:
            kwargs.update(login=self.login, password=self.password.get_secret_value())
            if self.server:
                kwargs["server"] = self.server
        return kwargs


def get_settings(env_file: str | None = None) -> MT5Settings:
    options: dict[str, Any] = {"_env_file": env_file} if env_file is not None else {}
    return MT5Settings(**options)
