from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import (
    get_security_config,
    set_operator_service,
    set_security_config,
)
from src.operator_api.observability.middleware import RequestTraceMiddleware
from src.operator_api.router import router
from src.operator_api.web_router import router as web_router
from src.operator_service.service import OperatorService

_ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = _ROOT / "web" / "dist"
if not os.getenv("CQM_SKIP_DOTENV"):  # tests must never read real credentials
    load_dotenv(_ROOT / ".env")  # an explicit process variable wins


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
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Observability, metrics collection, and request tracing middleware
    application.add_middleware(RequestTraceMiddleware)

    application.include_router(router)
    application.include_router(web_router)
    # The built web interface, if present, is served from the same address as
    # the API. Mounted last so API routes always win.
    if WEB_DIST.is_dir():
        application.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return application


app = create_app()
