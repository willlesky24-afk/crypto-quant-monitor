from __future__ import annotations

import logging
import os

from src.ai_agent.interfaces import BaseAIProvider, MockAIProvider
from src.ai_providers.providers.gemini import GeminiProvider
from src.ai_providers.providers.ollama import OllamaProvider
from src.ai_providers.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory creating isolated LLM providers based on environment configuration or explicit parameter."""

    @staticmethod
    def create_provider(
        provider_name: str | None = None,
        **kwargs,
    ) -> BaseAIProvider:
        """Create and return an AI provider instance.

        Supported provider names:
        - "gemini": Google Gemini API
        - "openai": OpenAI API
        - "ollama": Local Ollama instance
        - "mock": Offline deterministic mock provider (default)
        """
        name = (provider_name or os.getenv("AI_PROVIDER", "mock")).strip().lower()

        if name == "gemini":
            logger.info("Initializing Google Gemini AI Provider.")
            return GeminiProvider(**kwargs)
        elif name == "openai":
            logger.info("Initializing OpenAI Provider.")
            return OpenAIProvider(**kwargs)
        elif name == "ollama":
            logger.info("Initializing Local Ollama Provider.")
            return OllamaProvider(**kwargs)
        elif name == "mock":
            logger.info("Initializing Mock AI Provider.")
            return MockAIProvider()
        else:
            logger.warning(f"Unknown AI_PROVIDER '{name}'. Falling back to MockAIProvider.")
            return MockAIProvider()