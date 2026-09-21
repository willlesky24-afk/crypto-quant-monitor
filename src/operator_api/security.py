from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from typing import NamedTuple

from fastapi import Header, HTTPException, Request, status

from src.operator_api.config import APISecurityConfig


class RateLimitResult(NamedTuple):
    """Outcome of a rate limit check."""

    allowed: bool
    remaining: int
    retry_after: int


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter per client key."""

    def __init__(self, limit_per_minute: int = 60) -> None:
        self.limit_per_minute = limit_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> RateLimitResult:
        """Evaluate whether a request from the given key is permitted within the 60s sliding window."""
        now = time.time()
        window_start = now - 60.0
        q = self._requests[key]

        while q and q[0] < window_start:
            q.popleft()

        if len(q) >= self.limit_per_minute:
            oldest = q[0]
            retry_after = max(1, int(60.0 - (now - oldest)))
            return RateLimitResult(allowed=False, remaining=0, retry_after=retry_after)

        q.append(now)
        remaining = max(0, self.limit_per_minute - len(q))
        return RateLimitResult(allowed=True, remaining=remaining, retry_after=0)

    def reset(self) -> None:
        """Clear all active rate-limiting windows."""
        self._requests.clear()


def get_client_identifier(request: Request) -> str:
    """Extract a unique client identifier from headers or remote host."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{api_key}"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        return f"ip:{client_ip}"

    if request.client and request.client.host:
        return f"ip:{request.client.host}"

    return "unknown"


class SecurityGuard:
    """Security verification component handling API Key validation and rate limiting."""

    def __init__(
        self,
        config: APISecurityConfig,
        rate_limiter: InMemoryRateLimiter | None = None,
    ) -> None:
        self.config = config
        self.rate_limiter = rate_limiter or InMemoryRateLimiter(
            limit_per_minute=config.rate_limit_per_minute
        )

    def verify_auth(
        self,
        request: Request,
        x_api_key: str | None = Header(None, alias="X-API-Key"),
    ) -> None:
        """Validate API key credentials if security is enabled."""
        if not self.config.security_enabled:
            return

        path = request.url.path.rstrip("/")
        if path == "/health" and not self.config.require_auth_for_health:
            return

        expected = self.config.api_key
        if not expected:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security is enabled but no server API key was configured.",
            )

        if not x_api_key or not secrets.compare_digest(x_api_key, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid or missing API key. Provide X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    def enforce_rate_limit(self, request: Request) -> None:
        """Check and enforce request frequency limits."""
        if not self.config.rate_limit_enabled:
            return

        client_id = get_client_identifier(request)
        result = self.rate_limiter.check(client_id)

        if not result.allowed:
            from src.operator_api.observability.metrics import get_metrics_collector

            get_metrics_collector().record_rate_limit_rejection()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please reduce request frequency.",
                headers={"Retry-After": str(result.retry_after)},
            )
