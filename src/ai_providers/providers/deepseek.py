from __future__ import annotations

import os

from src.ai_providers.providers.openai import OpenAIProvider

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek through its OpenAI-compatible chat endpoint.

    The Copilot passes a Gemini model name to whichever provider is active, so a
    model that is not DeepSeek's is ignored. The default is overridable with
    DEEPSEEK_MODEL because model names change over time.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        own_model = model if model and model.startswith("deepseek") else None
        super().__init__(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY", "") or "",
            model=own_model or os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        if not (api_key or os.getenv("DEEPSEEK_API_KEY")):
            self.api_key = ""  # never fall through to OPENAI_API_KEY
        self.url = DEEPSEEK_URL
