from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class APISecurityConfig:
    """Configuration for API security, authentication, CORS, and rate limiting."""

    api_key: str | None = None
    security_enabled: bool = False
    rate_limit_per_minute: int = 60
    rate_limit_enabled: bool = False
    cors_origins: tuple[str, ...] = ("*",)
    require_auth_for_health: bool = False

    @classmethod
    def from_env(cls) -> APISecurityConfig:
        """Construct configuration by reading environment variables."""
        api_key = os.getenv("OPERATOR_API_KEY")

        sec_env = os.getenv("OPERATOR_API_SECURITY_ENABLED")
        if sec_env is not None:
            sec_enabled = sec_env.strip().lower() in ("true", "1", "yes")
        else:
            sec_enabled = bool(api_key and api_key.strip())

        rate_limit_env = os.getenv("OPERATOR_API_RATE_LIMIT_PER_MINUTE", "60")
        try:
            rate_limit_val = int(rate_limit_env)
        except ValueError:
            rate_limit_val = 60

        rate_limit_enabled_env = os.getenv("OPERATOR_API_RATE_LIMIT_ENABLED")
        if rate_limit_enabled_env is not None:
            rate_limit_enabled = rate_limit_enabled_env.strip().lower() in ("true", "1", "yes")
        else:
            rate_limit_enabled = False

        cors_env = os.getenv("OPERATOR_API_CORS_ORIGINS")
        if cors_env:
            cors_origins = tuple(o.strip() for o in cors_env.split(",") if o.strip())
        else:
            cors_origins = ("*",)

        health_auth_env = os.getenv("OPERATOR_API_REQUIRE_AUTH_FOR_HEALTH", "false")
        require_health_auth = health_auth_env.strip().lower() in ("true", "1", "yes")

        return cls(
            api_key=api_key.strip() if api_key else None,
            security_enabled=sec_enabled,
            rate_limit_per_minute=rate_limit_val,
            rate_limit_enabled=rate_limit_enabled,
            cors_origins=cors_origins,
            require_auth_for_health=require_health_auth,
        )
