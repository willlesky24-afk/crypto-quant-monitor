from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import (
    get_security_config,
    set_operator_service,
    set_security_config,
)
from src.operator_api.observability.middleware import RequestTraceMiddleware
from src.operator_api.router import router
from src.operator_service.service import OperatorService


def create_app(
    service: OperatorService | None = None,
    config: APISecurityConfig | None = None,
) -> FastAPI:
    """Factory creating the FastAPI Operator Gateway application.

    Args:
        service: Optional OperatorService instance to bind into dependencies.
        config: Optional APISecurityConfig to configure security, CORS, and rate limiting.

    Returns:
        Configured FastAPI application instance with security and CORS enabled.
    """
    if service is not None:
        set_operator_service(service)

    if config is not None:
        set_security_config(config)
        active_config = config
    else:
        active_config = get_security_config()

    application = FastAPI(
        title="Crypto Quant Monitor — AI Operator Gateway",
        description=(
            "Read-only API gateway exposing AI interpretation, signal explanations, "
            "and market briefings from the quantitative system."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Production-safe CORS middleware configuration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_config.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    # Observability, metrics collection, and request tracing middleware
    application.add_middleware(RequestTraceMiddleware)

    application.include_router(router)
    return application


app = create_app()

