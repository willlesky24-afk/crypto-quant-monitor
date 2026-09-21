from __future__ import annotations

import math
import threading
from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Thread-safe in-memory metrics registry for HTTP and business telemetry.

    Supports:
    - HTTP request counters by method, path, and status code.
    - Gauge of currently active in-flight requests.
    - Latency statistics (count, sum, min, max, average, and p50/p95/p99 quantiles).
    - Rate limit rejection counts.
    - Signal explanation & market summary requests and errors.
    - Context bridge events processed.
    - Stored records and active tracked symbols gauges.
    - Exporters for Prometheus OpenMetrics text format and JSON dictionary.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._total_requests: int = 0
        self._active_requests: int = 0
        self._requests_by_route: dict[tuple[str, str, int], int] = defaultdict(int)
        self._latencies: list[float] = []  # stored in seconds
        self._rate_limit_rejections: int = 0
        self._explanation_requests: int = 0
        self._explanation_errors: int = 0
        self._summary_requests: int = 0
        self._summary_errors: int = 0
        self._bridge_events_processed: int = 0
        self._stored_records_count: int = 0
        self._active_symbols_count: int = 0

    def record_request_start(self) -> None:
        """Increment active in-flight requests counter."""
        with self._lock:
            self._active_requests += 1

    def record_request_complete(
        self, method: str, path: str, status_code: int, duration_sec: float
    ) -> None:
        """Record completed HTTP request metrics."""
        with self._lock:
            self._total_requests += 1
            self._active_requests = max(0, self._active_requests - 1)
            norm_method = method.upper()
            norm_path = path if path else "/"
            self._requests_by_route[(norm_method, norm_path, status_code)] += 1
            self._latencies.append(max(0.0, duration_sec))

    def record_rate_limit_rejection(self) -> None:
        """Increment rate limit rejection counter."""
        with self._lock:
            self._rate_limit_rejections += 1

    def record_explanation_request(self, success: bool = True) -> None:
        """Record a signal explanation request."""
        with self._lock:
            self._explanation_requests += 1
            if not success:
                self._explanation_errors += 1

    def record_summary_request(self, success: bool = True) -> None:
        """Record a market summary request."""
        with self._lock:
            self._summary_requests += 1
            if not success:
                self._summary_errors += 1

    def record_bridge_event(self) -> None:
        """Increment count of processed context bridge events."""
        with self._lock:
            self._bridge_events_processed += 1

    def set_storage_metrics(self, records_count: int, active_symbols_count: int) -> None:
        """Update gauges for stored records and active symbols."""
        with self._lock:
            self._stored_records_count = max(0, records_count)
            self._active_symbols_count = max(0, active_symbols_count)

    def get_latency_stats(self) -> dict[str, float]:
        """Compute latency distribution metrics (in milliseconds)."""
        with self._lock:
            if not self._latencies:
                return {
                    "count": 0.0,
                    "min_ms": 0.0,
                    "max_ms": 0.0,
                    "avg_ms": 0.0,
                    "p50_ms": 0.0,
                    "p95_ms": 0.0,
                    "p99_ms": 0.0,
                }

            sorted_ms = sorted(s * 1000.0 for s in self._latencies)
            n = len(sorted_ms)

            def quantile(p: float) -> float:
                idx = int(math.ceil(p * n)) - 1
                return sorted_ms[max(0, min(idx, n - 1))]

            return {
                "count": float(n),
                "min_ms": round(sorted_ms[0], 2),
                "max_ms": round(sorted_ms[-1], 2),
                "avg_ms": round(sum(sorted_ms) / n, 2),
                "p50_ms": round(quantile(0.50), 2),
                "p95_ms": round(quantile(0.95), 2),
                "p99_ms": round(quantile(0.99), 2),
            }

    def reset(self) -> None:
        """Reset all metrics to initial states."""
        with self._lock:
            self._total_requests = 0
            self._active_requests = 0
            self._requests_by_route.clear()
            self._latencies.clear()
            self._rate_limit_rejections = 0
            self._explanation_requests = 0
            self._explanation_errors = 0
            self._summary_requests = 0
            self._summary_errors = 0
            self._bridge_events_processed = 0
            self._stored_records_count = 0
            self._active_symbols_count = 0

    def to_dict(self) -> dict[str, Any]:
        """Return structured JSON telemetry snapshot."""
        with self._lock:
            lat = self.get_latency_stats()
            by_route = [
                {
                    "method": m,
                    "path": p,
                    "status_code": sc,
                    "count": cnt,
                }
                for (m, p, sc), cnt in sorted(self._requests_by_route.items())
            ]
            return {
                "http_requests_total": self._total_requests,
                "http_requests_active": self._active_requests,
                "rate_limit_rejections_total": self._rate_limit_rejections,
                "explanation_requests_total": self._explanation_requests,
                "explanation_errors_total": self._explanation_errors,
                "summary_requests_total": self._summary_requests,
                "summary_errors_total": self._summary_errors,
                "bridge_events_processed_total": self._bridge_events_processed,
                "stored_records_count": self._stored_records_count,
                "active_symbols_count": self._active_symbols_count,
                "latency_stats": lat,
                "requests_by_route": by_route,
            }

    def to_prometheus_text(self) -> str:
        """Export metrics in standard Prometheus exposition format."""
        with self._lock:
            lines: list[str] = []

            # http_requests_total
            lines.append("# HELP http_requests_total Total number of HTTP requests processed.")
            lines.append("# TYPE http_requests_total counter")
            if self._requests_by_route:
                for (method, path, status_code), count in sorted(self._requests_by_route.items()):
                    lines.append(
                        f'http_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}'
                    )
            else:
                lines.append("http_requests_total 0")

            # http_requests_active
            lines.append("# HELP http_requests_active Current number of active in-flight HTTP requests.")
            lines.append("# TYPE http_requests_active gauge")
            lines.append(f"http_requests_active {self._active_requests}")

            # rate_limit_rejections_total
            lines.append("# HELP rate_limit_rejections_total Total number of rejected requests due to rate limiting.")
            lines.append("# TYPE rate_limit_rejections_total counter")
            lines.append(f"rate_limit_rejections_total {self._rate_limit_rejections}")

            # explanation_requests_total
            lines.append("# HELP explanation_requests_total Total signal explanation requests received.")
            lines.append("# TYPE explanation_requests_total counter")
            lines.append(f"explanation_requests_total {self._explanation_requests}")

            # explanation_errors_total
            lines.append("# HELP explanation_errors_total Total signal explanation generation failures.")
            lines.append("# TYPE explanation_errors_total counter")
            lines.append(f"explanation_errors_total {self._explanation_errors}")

            # summary_requests_total
            lines.append("# HELP summary_requests_total Total market summary requests received.")
            lines.append("# TYPE summary_requests_total counter")
            lines.append(f"summary_requests_total {self._summary_requests}")

            # summary_errors_total
            lines.append("# HELP summary_errors_total Total market summary generation failures.")
            lines.append("# TYPE summary_errors_total counter")
            lines.append(f"summary_errors_total {self._summary_errors}")

            # bridge_events_processed_total
            lines.append("# HELP bridge_events_processed_total Total closed candle signal events processed by context bridge.")
            lines.append("# TYPE bridge_events_processed_total counter")
            lines.append(f"bridge_events_processed_total {self._bridge_events_processed}")

            # stored_records_count
            lines.append("# HELP stored_records_count Total context snapshots currently in persistent storage.")
            lines.append("# TYPE stored_records_count gauge")
            lines.append(f"stored_records_count {self._stored_records_count}")

            # active_symbols_count
            lines.append("# HELP active_symbols_count Distinct symbols currently tracked in context storage.")
            lines.append("# TYPE active_symbols_count gauge")
            lines.append(f"active_symbols_count {self._active_symbols_count}")

            # latency summary
            lat = self.get_latency_stats()
            lines.append("# HELP http_request_duration_seconds HTTP request duration statistics in seconds.")
            lines.append("# TYPE http_request_duration_seconds summary")
            count = int(lat["count"])
            sum_sec = sum(self._latencies) if self._latencies else 0.0
            lines.append(f'http_request_duration_seconds{{quantile="0.5"}} {lat["p50_ms"] / 1000.0:.4f}')
            lines.append(f'http_request_duration_seconds{{quantile="0.95"}} {lat["p95_ms"] / 1000.0:.4f}')
            lines.append(f'http_request_duration_seconds{{quantile="0.99"}} {lat["p99_ms"] / 1000.0:.4f}')
            lines.append(f"http_request_duration_seconds_sum {sum_sec:.4f}")
            lines.append(f"http_request_duration_seconds_count {count}")

            lines.append("")
            return "\n".join(lines)


# Global default instance
_global_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Return the global MetricsCollector instance."""
    return _global_metrics_collector
