from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor

import pandas as pd

from src.notifications.channels.base import BaseNotificationChannel
from src.notifications.models import (
    NotificationChannelType,
    NotificationPayload,
    NotificationPriority,
    NotificationResult,
    SignalEvent,
)

logger = logging.getLogger(__name__)


class CooldownManager:
    """In-memory rate limiting and anti-spam tracker for signal notifications."""

    def __init__(self, default_cooldown_seconds: float = 300.0) -> None:
        self.default_cooldown_seconds = default_cooldown_seconds
        # Key: (symbol, timeframe, action) -> timestamp of last dispatch
        self._last_dispatched: dict[tuple[str, str, str], pd.Timestamp] = {}

    def is_in_cooldown(
        self,
        symbol: str,
        timeframe: str,
        action: str,
        now: pd.Timestamp | None = None,
        cooldown_seconds: float | None = None,
    ) -> bool:
        """Check if an alert for (symbol, timeframe, action) is currently on cooldown."""
        key = (symbol.strip().upper(), timeframe.strip().lower(), action.strip().upper())
        if key not in self._last_dispatched:
            return False

        current_time = now or pd.Timestamp.now("UTC")
        last_time = self._last_dispatched[key]
        cd = cooldown_seconds if cooldown_seconds is not None else self.default_cooldown_seconds

        elapsed = (current_time - last_time).total_seconds()
        return elapsed < cd

    def record_dispatch(
        self,
        symbol: str,
        timeframe: str,
        action: str,
        now: pd.Timestamp | None = None,
    ) -> None:
        """Record the timestamp of an alert dispatch."""
        key = (symbol.strip().upper(), timeframe.strip().lower(), action.strip().upper())
        self._last_dispatched[key] = now or pd.Timestamp.now("UTC")

    def reset(self) -> None:
        """Clear all cooldown history."""
        self._last_dispatched.clear()


class NotificationDispatcher:
    """Central orchestrator for filtering, rate limiting, and routing signal notifications."""

    def __init__(
        self,
        channels: list[BaseNotificationChannel] | None = None,
        cooldown_manager: CooldownManager | None = None,
        min_predictive_score: float = 0.60,
        min_confidence: float = 0.60,
        ignore_actions: set[str] | None = None,
        cooldown_seconds: float = 300.0,
        allow_critical_bypass: bool = True,
        max_workers: int = 4,
    ) -> None:
        self.channels: list[BaseNotificationChannel] = list(channels or [])
        self.cooldown_manager = cooldown_manager or CooldownManager(default_cooldown_seconds=cooldown_seconds)
        self.min_predictive_score = min_predictive_score
        self.min_confidence = min_confidence
        self.ignore_actions = {a.upper() for a in (ignore_actions or {"WAIT"})}
        self.allow_critical_bypass = allow_critical_bypass
        self.max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None

    def register_channel(self, channel: BaseNotificationChannel) -> None:
        """Register a notification delivery channel."""
        if any(c.name == channel.name for c in self.channels):
            logger.warning(f"Channel '{channel.name}' is already registered. Updating registration.")
            self.unregister_channel(channel.name)
        self.channels.append(channel)

    def unregister_channel(self, name: str) -> bool:
        """Unregister a channel by its unique name."""
        initial_count = len(self.channels)
        self.channels = [c for c in self.channels if c.name != name]
        return len(self.channels) < initial_count

    def should_dispatch(self, payload: NotificationPayload) -> tuple[bool, str | None]:
        """Evaluate whether a payload qualifies for dispatch based on filters and cooldown."""
        # 1. Filter out ignored actions (e.g. routine WAIT states) unless marked CRITICAL
        if payload.action.upper() in self.ignore_actions and payload.priority != NotificationPriority.CRITICAL:
            return False, f"Action '{payload.action}' is configured to be ignored."

        # 2. Check confidence and predictive score thresholds (CRITICAL and HIGH bypass score check)
        if payload.priority not in (NotificationPriority.CRITICAL, NotificationPriority.HIGH):
            if payload.predictive_score < self.min_predictive_score:
                return (
                    False,
                    f"Predictive score {payload.predictive_score:.2f} is below minimum threshold {self.min_predictive_score:.2f}.",
                )
            if payload.confidence < self.min_confidence:
                return (
                    False,
                    f"Confidence {payload.confidence:.2f} is below minimum threshold {self.min_confidence:.2f}.",
                )

        # 3. Check anti-spam cooldown
        if self.allow_critical_bypass and payload.priority == NotificationPriority.CRITICAL:
            return True, None

        if self.cooldown_manager.is_in_cooldown(payload.symbol, payload.timeframe, payload.action):
            return (
                False,
                f"Alert for {payload.symbol} [{payload.timeframe}] {payload.action} is currently in cooldown.",
            )

        return True, None

    def dispatch(self, payload: NotificationPayload) -> list[NotificationResult]:
        """Synchronously dispatch a payload across all registered and enabled channels."""
        should_send, reason = self.should_dispatch(payload)
        if not should_send:
            logger.info(f"Notification suppressed: {reason}")
            return [
                NotificationResult(
                    success=False,
                    channel=NotificationChannelType.LOG,
                    error_message=f"Suppressed: {reason}",
                    event_id=payload.event_id,
                )
            ]

        results: list[NotificationResult] = []
        enabled_channels = [c for c in self.channels if c.is_enabled]
        if not enabled_channels:
            logger.warning("No enabled notification channels registered.")
            return results

        for channel in enabled_channels:
            try:
                res = channel.send(payload)
                results.append(res)
            except Exception as exc:
                logger.error(f"Unexpected exception dispatching to {channel.name}: {exc}", exc_info=True)
                results.append(
                    NotificationResult(
                        success=False,
                        channel=channel.channel_type,
                        error_message=f"Unhandled exception: {exc.__class__.__name__} - {str(exc)}",
                        event_id=payload.event_id,
                    )
                )

        # Record cooldown if at least one channel delivered successfully or simulated successfully
        if any(r.success for r in results):
            self.cooldown_manager.record_dispatch(payload.symbol, payload.timeframe, payload.action)

        return results

    def dispatch_signal(
        self,
        signal: SignalEvent,
        priority: NotificationPriority | None = None,
        custom_summary: str | None = None,
    ) -> list[NotificationResult]:
        """Convenience method to construct a NotificationPayload directly from a SignalEvent and dispatch."""
        payload = NotificationPayload.from_signal_event(
            event=signal,
            priority=priority,
            custom_summary=custom_summary,
        )
        return self.dispatch(payload)

    def dispatch_async(self, payload: NotificationPayload) -> Future[list[NotificationResult]]:
        """Submit dispatch to a background thread pool to prevent blocking the caller."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="notif-dispatch")
        return self._executor.submit(self.dispatch, payload)

    def close(self) -> None:
        """Shutdown background thread pool executor."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
