from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ServerSettings:
    """HTTP server and runtime execution settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    log_level: str = "info"


@dataclass(frozen=True)
class StorageSettings:
    """File, database, and historical columnar data storage paths."""

    data_dir: Path = field(default_factory=lambda: Path("data"))
    database_path: Path = field(default_factory=lambda: Path("data/market_contexts.db"))
    parquet_dir: Path = field(default_factory=lambda: Path("data/parquet"))


@dataclass(frozen=True)
class StreamingSettings:
    """Binance WebSocket live ingestion parameters."""

    symbols: tuple[str, ...] = ("BTCUSDT",)
    timeframe: str = "1h"
    buffer_size: int = 500


@dataclass(frozen=True)
class SecuritySettings:
    """API Gateway authentication, rate limiting, and CORS configuration."""

    api_key: str | None = None
    security_enabled: bool = False
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    cors_origins: tuple[str, ...] = ("*",)


@dataclass(frozen=True)
class ObservabilitySettings:
    """Metrics exposition, tracing, and structured logging configuration."""

    metrics_enabled: bool = True
    json_logging_enabled: bool = True


@dataclass(frozen=True)
class AIProviderSettings:
    """Configuration for LLM AI Provider integration."""

    provider: str = "mock"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    timeout_seconds: float = 10.0
    max_retries: int = 2


@dataclass(frozen=True)
class AppSettings:
    """Consolidated master application configuration container.

    Provides automatic environment variable ingestion and validation.

    """

    environment: str = "production"
    server: ServerSettings = field(default_factory=ServerSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    streaming: StreamingSettings = field(default_factory=StreamingSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    ai_provider: AIProviderSettings = field(default_factory=AIProviderSettings)

    @classmethod

    def from_env(cls) -> AppSettings:
        """Construct AppSettings resolving environment variable overrides."""
        # Environment
        env_name = os.getenv("ENVIRONMENT", "production").strip().lower()

        # Server
        host = os.getenv("SERVER_HOST", "0.0.0.0").strip()
        port = int(os.getenv("SERVER_PORT", "8000").strip())
        workers = int(os.getenv("SERVER_WORKERS", "1").strip())
        reload_val = os.getenv("SERVER_RELOAD", "false").strip().lower() in ("true", "1", "yes")
        log_level = os.getenv("LOG_LEVEL", "info").strip().lower()
        server = ServerSettings(
            host=host,
            port=port,
            workers=workers,
            reload=reload_val,
            log_level=log_level,
        )

        # Storage
        data_dir = Path(os.getenv("DATA_DIR", "data")).resolve()
        raw_db = os.getenv("DATABASE_PATH", str(data_dir / "market_contexts.db")).strip()
        database_path = Path(raw_db).resolve()
        parquet_dir = Path(os.getenv("PARQUET_DIR", str(data_dir / "parquet"))).resolve()
        storage = StorageSettings(
            data_dir=data_dir,
            database_path=database_path,
            parquet_dir=parquet_dir,
        )

        # Streaming
        raw_symbols = (os.getenv("SYMBOLS") or os.getenv("SYMBOL", "BTCUSDT")).strip()
        symbols = tuple(s.strip().upper() for s in raw_symbols.split(",") if s.strip())
        timeframe = os.getenv("TIMEFRAME", "1h").strip().lower()
        buffer_size = int(os.getenv("STREAMING_BUFFER_SIZE", "500").strip())
        streaming = StreamingSettings(
            symbols=symbols or ("BTCUSDT",),
            timeframe=timeframe,
            buffer_size=buffer_size,
        )

        # Security
        api_key = os.getenv("OPERATOR_API_KEY", "").strip() or None
        sec_enabled = os.getenv("OPERATOR_API_SECURITY_ENABLED", "false").strip().lower() in (
            "true",
            "1",
            "yes",
        )
        rl_enabled = os.getenv("OPERATOR_API_RATE_LIMIT_ENABLED", "true").strip().lower() in (
            "true",
            "1",
            "yes",
        )
        rl_limit = int(os.getenv("OPERATOR_API_RATE_LIMIT_PER_MINUTE", "60").strip())
        raw_cors = os.getenv("OPERATOR_API_CORS_ORIGINS", "*").strip()
        cors = tuple(c.strip() for c in raw_cors.split(",") if c.strip())
        security = SecuritySettings(
            api_key=api_key,
            security_enabled=sec_enabled,
            rate_limit_enabled=rl_enabled,
            rate_limit_per_minute=rl_limit,
            cors_origins=cors or ("*",),
        )

        # Observability
        metrics_enabled = os.getenv("METRICS_ENABLED", "true").strip().lower() in (
            "true",
            "1",
            "yes",
        )
        json_logging = os.getenv("JSON_LOGGING_ENABLED", "true").strip().lower() in (
            "true",
            "1",
            "yes",
        )
        observability = ObservabilitySettings(
            metrics_enabled=metrics_enabled,
            json_logging_enabled=json_logging,
        )

        # AI Provider
        ai_provider_name = os.getenv("AI_PROVIDER", "mock").strip().lower()
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip() or None
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").strip()
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3").strip()
        timeout_sec = float(os.getenv("LLM_TIMEOUT_SECONDS", "10.0").strip())
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "2").strip())

        ai_provider = AIProviderSettings(
            provider=ai_provider_name,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            ollama_url=ollama_url,
            ollama_model=ollama_model,
            timeout_seconds=timeout_sec,
            max_retries=max_retries,
        )

        return cls(
            environment=env_name,
            server=server,
            storage=storage,
            streaming=streaming,
            security=security,
            observability=observability,
            ai_provider=ai_provider,
        )


    def ensure_directories(self) -> None:
        """Create target data and logs directories if they do not exist."""
        self.storage.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage.parquet_dir.mkdir(parents=True, exist_ok=True)


# Default global settings instance
settings = AppSettings.from_env()
