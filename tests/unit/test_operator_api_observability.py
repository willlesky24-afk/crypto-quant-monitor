from __future__ import annotations

import json
import logging
import threading

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.operator_api.app import create_app
from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import (
    reset_operator_service,
    reset_security_config,
)
from src.operator_api.observability.logging import StructuredLogFormatter
from src.operator_api.observability.metrics import (
    MetricsCollector,
    get_metrics_collector,
)
from src.operator_api.observability.middleware import RequestTraceMiddleware
from src.operator_service.interfaces import (
    BaseMarketContextProvider,
    InMemoryMarketContextProvider,
)
from src.operator_service.service import OperatorService
from src.operator_service.storage.sqlite_provider import SQLiteMarketContextProvider


def _create_mock_context(symbol: str = "BTCUSDT", price: float = 65000.0) -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-03-30 12:00:00"),
        symbol=symbol,
        timeframe="1h",
        current_price=price,
        market_regime="BULL_TREND",
        predictive_score=0.82,
        quant_score=86.0,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.85,
            reasoning="Trend confirmed",
            positives=("Volume surge",),
            warnings=(),
        ),
        risk=RiskMetrics(stop_loss=63500.0, take_profit=68000.0),
        technical_indicators={"rsi": 34.0},
        volume_profile={"poc": 64800.0},
    )


class TestMetricsCollector:
    def test_initial_state(self):
        collector = MetricsCollector()
        d = collector.to_dict()
        assert d["http_requests_total"] == 0
        assert d["http_requests_active"] == 0
        assert d["rate_limit_rejections_total"] == 0
        assert d["explanation_requests_total"] == 0
        assert d["summary_requests_total"] == 0
        assert d["latency_stats"]["count"] == 0.0

    def test_record_requests_and_latency_quantiles(self):
        collector = MetricsCollector()
        collector.record_request_start()
        assert collector.to_dict()["http_requests_active"] == 1

        # Record varied latencies (0.01s to 0.10s)
        for i in range(1, 11):
            collector.record_request_complete("GET", "/test", 200, i * 0.01)

        d = collector.to_dict()
        assert d["http_requests_total"] == 10
        assert d["http_requests_active"] == 0
        lat = d["latency_stats"]
        assert lat["count"] == 10.0
        assert lat["min_ms"] == 10.0
        assert lat["max_ms"] == 100.0
        assert lat["p50_ms"] == 50.0
        assert lat["p95_ms"] == 100.0
        assert lat["p99_ms"] == 100.0

    def test_business_and_bridge_counters(self):
        collector = MetricsCollector()
        collector.record_rate_limit_rejection()
        collector.record_explanation_request(success=True)
        collector.record_explanation_request(success=False)
        collector.record_summary_request(success=True)
        collector.record_summary_request(success=False)
        collector.record_bridge_event()
        collector.set_storage_metrics(records_count=42, active_symbols_count=3)

        d = collector.to_dict()
        assert d["rate_limit_rejections_total"] == 1
        assert d["explanation_requests_total"] == 2
        assert d["explanation_errors_total"] == 1
        assert d["summary_requests_total"] == 2
        assert d["summary_errors_total"] == 1
        assert d["bridge_events_processed_total"] == 1
        assert d["stored_records_count"] == 42
        assert d["active_symbols_count"] == 3

    def test_prometheus_exposition_format(self):
        collector = MetricsCollector()
        collector.record_request_complete("GET", "/health", 200, 0.025)
        collector.record_rate_limit_rejection()
        collector.set_storage_metrics(10, 2)

        prom = collector.to_prometheus_text()
        assert "# HELP http_requests_total" in prom
        assert "# TYPE http_requests_total counter" in prom
        assert 'http_requests_total{method="GET",path="/health",status="200"} 1' in prom
        assert "http_requests_active 0" in prom
        assert "rate_limit_rejections_total 1" in prom
        assert "stored_records_count 10" in prom
        assert "active_symbols_count 2" in prom
        assert "http_request_duration_seconds_count 1" in prom

    def test_prometheus_empty_exposition(self):
        collector = MetricsCollector()
        prom = collector.to_prometheus_text()
        assert "http_requests_total 0" in prom
        assert "http_requests_active 0" in prom

    def test_thread_safety(self):
        collector = MetricsCollector()

        def worker():
            for _ in range(50):
                collector.record_request_start()
                collector.record_request_complete("POST", "/batch", 200, 0.005)
                collector.record_bridge_event()

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        d = collector.to_dict()
        assert d["http_requests_total"] == 250
        assert d["bridge_events_processed_total"] == 250
        assert d["http_requests_active"] == 0

    def test_reset(self):
        collector = MetricsCollector()
        collector.record_request_complete("GET", "/api", 200, 0.01)
        collector.reset()
        assert collector.to_dict()["http_requests_total"] == 0

    def test_global_singleton(self):
        c1 = get_metrics_collector()
        c2 = get_metrics_collector()
        assert c1 is c2


class TestStructuredLogging:
    def test_formatter_basic_log(self):
        formatter = StructuredLogFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="User access granted",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "User access granted"
        assert "timestamp" in data

    def test_formatter_with_tracing_and_exception(self):
        formatter = StructuredLogFormatter()
        try:
            raise ValueError("Test error trace")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="api.access",
            level=logging.ERROR,
            pathname=__file__,
            lineno=20,
            msg="Request failed",
            args=(),
            exc_info=exc_info,
        )
        record.request_id = "req-12345"
        record.client_ip = "127.0.0.1"
        record.duration_ms = 45.2

        output = formatter.format(record)
        data = json.loads(output)
        assert data["request_id"] == "req-12345"
        assert data["client_ip"] == "127.0.0.1"
        assert data["duration_ms"] == 45.2
        assert "exception" in data
        assert "ValueError: Test error trace" in data["exception"]


class TestRequestTraceMiddleware:
    def test_request_headers_and_timing(self):
        collector = MetricsCollector()
        app = FastAPI()
        app.add_middleware(RequestTraceMiddleware, metrics_collector=collector)

        @app.get("/ping")
        def ping():
            return {"ping": "pong"}

        client = TestClient(app)
        res = client.get("/ping", headers={"X-Request-ID": "custom-trace-id"})

        assert res.status_code == 200
        assert res.headers["X-Request-ID"] == "custom-trace-id"
        assert "X-Response-Time-Ms" in res.headers
        assert float(res.headers["X-Response-Time-Ms"]) >= 0.0

        d = collector.to_dict()
        assert d["http_requests_total"] == 1

    def test_generated_request_id_when_missing(self):
        collector = MetricsCollector()
        app = FastAPI()
        app.add_middleware(RequestTraceMiddleware, metrics_collector=collector)

        @app.get("/auto-id")
        def auto_id():
            return {"ok": True}

        client = TestClient(app)
        res = client.get("/auto-id")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers
        assert len(res.headers["X-Request-ID"]) > 10

    def test_exception_handling_in_middleware(self):
        collector = MetricsCollector()
        app = FastAPI()
        app.add_middleware(RequestTraceMiddleware, metrics_collector=collector)

        @app.get("/fail")
        def fail():
            raise RuntimeError("Intentional server crash")

        client = TestClient(app, raise_server_exceptions=False)
        res = client.get("/fail")
        assert res.status_code == 500

        d = collector.to_dict()
        assert d["http_requests_total"] == 1
        assert d["requests_by_route"][0]["status_code"] == 500


class TestObservabilityEndpoints:
    def setup_method(self):
        reset_operator_service()
        reset_security_config()
        get_metrics_collector().reset()

    def teardown_method(self):
        reset_operator_service()
        reset_security_config()
        get_metrics_collector().reset()

    def test_metrics_endpoint(self):
        provider = InMemoryMarketContextProvider()
        provider.update_context(_create_mock_context("BTCUSDT"))
        service = OperatorService(context_provider=provider)
        config = APISecurityConfig(security_enabled=False)
        app = create_app(service=service, config=config)
        client = TestClient(app)

        res = client.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        assert "http_requests_total" in res.text
        assert "active_symbols_count 1" in res.text

    def test_health_ready_with_sqlite_provider(self):
        sqlite_provider = SQLiteMarketContextProvider()
        sqlite_provider.update_context(_create_mock_context("BTCUSDT"))
        sqlite_provider.update_context(_create_mock_context("ETHUSDT"))
        service = OperatorService(context_provider=sqlite_provider)
        config = APISecurityConfig(security_enabled=False)
        app = create_app(service=service, config=config)
        client = TestClient(app)

        res = client.get("/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "READY"
        assert data["storage_healthy"] is True
        assert data["tracked_symbols_count"] == 2
        assert data["total_records_count"] == 2
        assert "available_symbols" in data["details"]
        sqlite_provider.close()

    def test_health_ready_unhealthy_storage(self):
        class BrokenProvider(BaseMarketContextProvider):
            async def get_latest_context(self, symbol: str, timeframe: str) -> MarketContext | None:
                return None

            async def get_available_symbols(self) -> list[str]:
                raise ConnectionError("Database disk is detached")

        service = OperatorService(context_provider=BrokenProvider())
        config = APISecurityConfig(security_enabled=False)
        app = create_app(service=service, config=config)
        client = TestClient(app)

        res = client.get("/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["detail"]["status"] == "NOT_READY"
        assert data["detail"]["storage_healthy"] is False
        assert "Database disk is detached" in data["detail"]["details"]["error"]

    def test_health_stats_endpoint(self):
        provider = InMemoryMarketContextProvider()
        provider.update_context(_create_mock_context("SOLUSDT"))
        service = OperatorService(context_provider=provider)
        config = APISecurityConfig(security_enabled=False)
        app = create_app(service=service, config=config)
        client = TestClient(app)

        # Make some calls to populate metrics
        client.get("/health")
        client.get("/signals/latest?symbol=SOLUSDT")

        res = client.get("/health/stats")
        assert res.status_code == 200
        data = res.json()
        assert data["http_requests_total"] >= 2
        assert data["explanation_requests_total"] == 1
        assert data["active_symbols_count"] == 1
        assert "latency_stats" in data
        assert "requests_by_route" in data

    def test_rate_limit_updates_metrics(self):
        provider = InMemoryMarketContextProvider()
        service = OperatorService(context_provider=provider)
        config = APISecurityConfig(
            security_enabled=True,
            api_key="valid-key",
            rate_limit_enabled=True,
            rate_limit_per_minute=2,
        )
        app = create_app(service=service, config=config)
        client = TestClient(app)
        headers = {"X-API-Key": "valid-key"}

        # Request 1 & 2 pass
        assert client.get("/health", headers=headers).status_code == 200
        assert client.get("/health", headers=headers).status_code == 200

        # Request 3 rejected
        res = client.get("/health", headers=headers)
        assert res.status_code == 429

        # Verify rejection recorded in metrics
        collector = get_metrics_collector()
        assert collector.to_dict()["rate_limit_rejections_total"] == 1
