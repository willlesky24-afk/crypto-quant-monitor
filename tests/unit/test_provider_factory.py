from __future__ import annotations

import os
from unittest.mock import patch

from src.ai_agent.interfaces import MockAIProvider
from src.ai_providers.factory import ProviderFactory
from src.ai_providers.providers.gemini import GeminiProvider
from src.ai_providers.providers.ollama import OllamaProvider
from src.ai_providers.providers.openai import OpenAIProvider


def test_provider_factory_mock():
    prov = ProviderFactory.create_provider("mock")
    assert isinstance(prov, MockAIProvider)


def test_provider_factory_gemini():
    prov = ProviderFactory.create_provider("gemini", api_key="test_key", model="gemini-2.5-flash")
    assert isinstance(prov, GeminiProvider)
    assert prov.api_key == "test_key"
    assert prov.model == "gemini-2.5-flash"


def test_provider_factory_openai():
    prov = ProviderFactory.create_provider("openai", api_key="sk-test", model="gpt-4o")
    assert isinstance(prov, OpenAIProvider)
    assert prov.api_key == "sk-test"
    assert prov.model == "gpt-4o"


def test_provider_factory_ollama():
    prov = ProviderFactory.create_provider("ollama", base_url="http://custom:11434", model="mistral")
    assert isinstance(prov, OllamaProvider)
    assert prov.base_url == "http://custom:11434"
    assert prov.model == "mistral"


def test_provider_factory_env_selection():
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "env_key"}):
        prov = ProviderFactory.create_provider()
        assert isinstance(prov, GeminiProvider)
        assert prov.api_key == "env_key"


def test_provider_factory_unknown_fallback():
    prov = ProviderFactory.create_provider("non_existent_provider")
    assert isinstance(prov, MockAIProvider)