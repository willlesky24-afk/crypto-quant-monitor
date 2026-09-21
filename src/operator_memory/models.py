from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# Sensitive pattern detection to safeguard operator memory
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(?:api[_-]?key|secret|password|private[_-]?key|token)\s*[:=]\s*['\"]?[\w\-_]{8,}['\"]?"),
    re.compile(r"\b(?:ey[A-Za-z0-9-_]{20,})\b"),  # JWT-like
    re.compile(r"\b[0-9a-fA-F]{64}\b"),  # Private hex key
]


@dataclass(frozen=True)
class MemoryEntry:
    """Represents a recorded operator note, query interaction, or asset observation."""

    id: str
    entry_type: str  # "query", "note", "observation"
    symbol: str
    content: str
    operator_id: str = "default_operator"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def sanitize_content(cls, raw_content: str) -> str:
        """Sanitize text to guarantee no private keys, exchange secrets, or sensitive tokens are stored."""
        sanitized = raw_content
        for pattern in SENSITIVE_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SENSITIVE_CREDENTIAL]", sanitized)
        return sanitized

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)