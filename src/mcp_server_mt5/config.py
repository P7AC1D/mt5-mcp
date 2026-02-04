"""Configuration management for MT5 MCP Server."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MT5Settings(BaseSettings):
    """MT5 connection settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MT5_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    login: int | None = None
    password: SecretStr | None = None
    server: str | None = None
    path: str | None = None

    @property
    def has_credentials(self) -> bool:
        """Check if login credentials are configured."""
        return self.login is not None and self.password is not None

    def get_init_kwargs(self) -> dict:
        """Get kwargs for mt5.initialize() call."""
        kwargs = {}
        if self.path:
            kwargs["path"] = self.path
        # Only include login credentials if all required fields are present
        if self.has_credentials:
            kwargs["login"] = self.login
            kwargs["password"] = self.password.get_secret_value()
            if self.server:
                kwargs["server"] = self.server
        return kwargs


def get_settings() -> MT5Settings:
    """Get MT5 settings instance."""
    return MT5Settings()
