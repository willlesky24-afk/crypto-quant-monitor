from __future__ import annotations

from typing import Any

from fastapi import Header, Request

from src.operator_api.config import APISecurityConfig
from src.operator_api.security import SecurityGuard
from src.operator_service.interfaces import InMemoryMarketContextProvider
from src.operator_service.service import OperatorService

_operator_service_instance: OperatorService | None = None
_security_config_instance: APISecurityConfig | None = None
_security_guard_instance: SecurityGuard | None = None


def get_operator_service() -> OperatorService:
    """Dependency provider for OperatorService.

    Returns the currently configured OperatorService instance, or initializes
    a default instance with an InMemoryMarketContextProvider.
    """
    global _operator_service_instance
    if _operator_service_instance is None:
        import os

        db_path = os.getenv("DATABASE_PATH")
        if db_path:
            try:
                from src.operator_service.storage.sqlite_provider import (
                    SQLiteMarketContextProvider,
                )

                provider = SQLiteMarketContextProvider(db_path=db_path)
            except Exception:
                provider = InMemoryMarketContextProvider()
        else:
            provider = InMemoryMarketContextProvider()

        _operator_service_instance = OperatorService(
            context_provider=provider
        )
    return _operator_service_instance


def set_operator_service(service: OperatorService) -> None:
    """Override the global OperatorService instance (useful for testing or custom wiring)."""
    global _operator_service_instance
    _operator_service_instance = service


def reset_operator_service() -> None:
    """Reset the global OperatorService instance to None."""
    global _operator_service_instance
    _operator_service_instance = None


def get_security_config() -> APISecurityConfig:
    """Return the currently configured APISecurityConfig, or loads from environment."""
    global _security_config_instance
    if _security_config_instance is None:
        _security_config_instance = APISecurityConfig.from_env()
    return _security_config_instance


def set_security_config(config: APISecurityConfig) -> None:
    """Set custom security configuration and resets the active guard."""
    global _security_config_instance, _security_guard_instance
    _security_config_instance = config
    _security_guard_instance = SecurityGuard(config=config)


def reset_security_config() -> None:
    """Reset security configuration and active guard to default state."""
    global _security_config_instance, _security_guard_instance
    _security_config_instance = None
    _security_guard_instance = None


def get_security_guard() -> SecurityGuard:
    """Return the active SecurityGuard instance."""
    global _security_guard_instance
    if _security_guard_instance is None:
        cfg = get_security_config()
        _security_guard_instance = SecurityGuard(config=cfg)
    return _security_guard_instance


def verify_security(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency that enforces rate limiting and API key verification."""
    guard = get_security_guard()
    guard.enforce_rate_limit(request)
    guard.verify_auth(request, x_api_key)


_assistant_instance: Any = None
_report_service_instance: Any = None
_anomaly_detector_instance: Any = None
_memory_instance: Any = None


def get_operator_assistant() -> Any:
    global _assistant_instance
    if _assistant_instance is None:
        from src.ai_providers.factory import ProviderFactory
        from src.operator_assistant.assistant import OperatorAssistant
        service = get_operator_service()
        ai_prov = ProviderFactory.create_provider()
        _assistant_instance = OperatorAssistant(
            context_provider=service.context_provider,
            ai_provider=ai_prov,
        )
    return _assistant_instance



def set_operator_assistant(assistant: Any) -> None:
    global _assistant_instance
    _assistant_instance = assistant


def get_market_report_service() -> Any:
    global _report_service_instance
    if _report_service_instance is None:
        from src.market_reports.generator import MarketReportService
        _report_service_instance = MarketReportService()
    return _report_service_instance


def set_market_report_service(service: Any) -> None:
    global _report_service_instance
    _report_service_instance = service


def get_anomaly_detector() -> Any:
    global _anomaly_detector_instance
    if _anomaly_detector_instance is None:
        from src.anomaly_detection.detector import MarketAnomalyDetector
        _anomaly_detector_instance = MarketAnomalyDetector()
    return _anomaly_detector_instance


def set_anomaly_detector(detector: Any) -> None:
    global _anomaly_detector_instance
    _anomaly_detector_instance = detector


def get_operator_memory() -> Any:
    global _memory_instance
    if _memory_instance is None:
        from src.operator_memory.sqlite_memory import SQLiteOperatorMemory
        _memory_instance = SQLiteOperatorMemory()
    return _memory_instance


def set_operator_memory(memory: Any) -> None:
    global _memory_instance
    _memory_instance = memory

