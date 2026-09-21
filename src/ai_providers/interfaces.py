from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.ai_agent.interfaces import BaseAIProvider
from src.ai_providers.models import AIResponse


class BaseLLMProvider(BaseAIProvider, ABC):
    """Abstract interface for modern external and local LLM integrations.

    Extends BaseAIProvider so it can be directly consumed by existing intelligence
    services while exposing a standardized generate_response method for prompts.
    """

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> AIResponse:
        """Execute inference against the LLM with strict error and timeout isolation."""
        ...