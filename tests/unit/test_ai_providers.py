from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.ai_providers.models import AIResponse
from src.ai_providers.providers.gemini import GeminiProvider
from src.ai_providers.providers.ollama import OllamaProvider
from src.ai_providers.providers.openai import OpenAIProvider


def _sample_context() -> MarketContext:
    import pandas as pd
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=64000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.80,
        quant_score=85.0,
        signal=SignalInfo(action="BUY", direction="LONG", confidence=0.88, positives=("Trend",)),
        risk=RiskMetrics(stop_loss=62000.0, take_profit=68000.0),
    )


@pytest.mark.anyio
async def test_gemini_provider_missing_key_fallback():
    provider = GeminiProvider(api_key="")
    res = await provider.generate_response("Test prompt")
    assert isinstance(res, AIResponse)
    assert res.provider == "gemini-fallback"
    assert "Gemini API key is not configured" in res.content
    assert res.tokens_used == 0


@pytest.mark.anyio
async def test_gemini_provider_successful_request():
    provider = GeminiProvider(api_key="valid_key", model="gemini-2.5-flash")
    mock_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "BTC is in a strong bullish trend above support."}]
                }
            }
        ],
        "usageMetadata": {"totalTokenCount": 42},
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = await provider.generate_response("Analyze BTC")
        assert res.provider == "gemini"
        assert "strong bullish trend" in res.content
        assert res.tokens_used == 42


@pytest.mark.anyio
async def test_gemini_provider_retry_and_failure():
    provider = GeminiProvider(api_key="valid_key", max_retries=1, timeout_seconds=1.0)
    with patch("urllib.request.urlopen", side_effect=Exception("HTTP 500 error")):
        res = await provider.generate_response("Analyze BTC")
        assert res.provider == "gemini-fallback"
        assert "Gemini API request failed" in res.content


@pytest.mark.anyio
async def test_gemini_provider_legacy_interfaces():
    provider = GeminiProvider(api_key="")
    ctx = _sample_context()
    expl = await provider.generate_explanation(ctx)
    assert "Gemini API key is not configured" in expl.summary
    assert expl.confidence == 0.88

    summary = await provider.summarize_market(ctx)
    assert "Gemini Market Briefing" in summary.title
    assert await provider.health_check() is True


@pytest.mark.anyio
async def test_openai_provider_missing_key_fallback():
    provider = OpenAIProvider(api_key="")
    res = await provider.generate_response("Test prompt")
    assert res.provider == "openai-fallback"
    assert "OpenAI API key is not configured" in res.content


@pytest.mark.anyio
async def test_openai_provider_successful_request():
    provider = OpenAIProvider(api_key="valid_key", model="gpt-4o-mini")
    mock_payload = {
        "choices": [
            {
                "message": {"content": "OpenAI: Price is holding above POC."}
            }
        ],
        "usage": {"total_tokens": 55},
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = await provider.generate_response("Analyze BTC")
        assert res.provider == "openai"
        assert "holding above POC" in res.content
        assert res.tokens_used == 55


@pytest.mark.anyio
async def test_openai_provider_retry_and_failure():
    provider = OpenAIProvider(api_key="valid_key", max_retries=1)
    with patch("urllib.request.urlopen", side_effect=Exception("Timeout")):
        res = await provider.generate_response("Analyze BTC")
        assert res.provider == "openai-fallback"
        assert "OpenAI API request failed" in res.content


@pytest.mark.anyio
async def test_openai_provider_legacy_interfaces():
    provider = OpenAIProvider(api_key="")
    ctx = _sample_context()
    expl = await provider.generate_explanation(ctx)
    assert "OpenAI API key is not configured" in expl.summary
    summary = await provider.summarize_market(ctx)
    assert "OpenAI Market Briefing" in summary.title
    assert await provider.health_check() is True


@pytest.mark.anyio
async def test_ollama_provider_successful_request():
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3")
    mock_payload = {
        "response": "Llama3: Volatility compression observed.",
        "eval_count": 60,
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = await provider.generate_response("Analyze BTC")
        assert res.provider == "ollama"
        assert "Volatility compression" in res.content
        assert res.tokens_used == 60


@pytest.mark.anyio
async def test_ollama_provider_failure():
    provider = OllamaProvider(base_url="http://invalid-host:11434", max_retries=1)
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        res = await provider.generate_response("Analyze BTC")
        assert res.provider == "ollama-fallback"
        assert "Local Ollama daemon unreachable" in res.content



@pytest.mark.anyio
async def test_ollama_provider_legacy_interfaces():
    provider = OllamaProvider(base_url="http://localhost:11434")
    with patch.object(provider, "generate_response", return_value=AIResponse(
        content="Ollama mock content", provider="ollama", model="llama3", latency_ms=10.0
    )):
        ctx = _sample_context()
        expl = await provider.generate_explanation(ctx)
        assert expl.summary == "Ollama mock content"
        summary = await provider.summarize_market(ctx)

        assert "Ollama Local Briefing" in summary.title
        assert await provider.health_check() is True


def test_ai_response_to_dict():
    resp = AIResponse(
        content="Market analysis text",
        provider="gemini",
        model="gemini-2.5-flash",
        latency_ms=15.2,
        tokens_used=45,
    )
    d = resp.to_dict()
    assert d["content"] == "Market analysis text"
    assert d["provider"] == "gemini"
    assert "DECISION SUPPORT ONLY" in resp.disclaimer