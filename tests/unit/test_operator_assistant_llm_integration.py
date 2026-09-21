from __future__ import annotations

import pandas as pd
import pytest

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.ai_providers.interfaces import BaseLLMProvider
from src.ai_providers.models import AIResponse
from src.operator_assistant.assistant import OperatorAssistant
from src.operator_assistant.models import OperatorQuery
from src.operator_service.interfaces import InMemoryMarketContextProvider


class MockLLM(BaseLLMProvider):
    def __init__(self, answer_text: str = "Mock LLM structured narrative.") -> None:
        self.answer_text = answer_text
        self.calls: list[str] = []

    async def generate_response(self, prompt: str, metadata: dict | None = None) -> AIResponse:
        self.calls.append(prompt)
        return AIResponse(
            content=self.answer_text,
            provider="test-llm",
            model="test-model",
            latency_ms=12.5,
            tokens_used=100,
        )

    async def generate_explanation(self, context: MarketContext):
        raise NotImplementedError

    async def summarize_market(self, context: MarketContext):
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


def _create_sample_context() -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=64000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.85,
        quant_score=88.0,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.90,
            positives=("EMA Alignment", "Volume Spike"),
        ),
        risk=RiskMetrics(stop_loss=62000.0, take_profit=68000.0),
    )


@pytest.mark.anyio
async def test_operator_assistant_llm_integration():
    provider = InMemoryMarketContextProvider()
    ctx = _create_sample_context()
    provider.update_context(ctx)

    mock_llm = MockLLM(answer_text="LLM: BTC is showing strong continuous demand above EMA 20.")
    assistant = OperatorAssistant(context_provider=provider, ai_provider=mock_llm)

    res = await assistant.ask(OperatorQuery(query="Analyze BTC right now", symbol="BTCUSDT"))

    assert len(mock_llm.calls) == 1
    assert "IMMUTABLE QUANTITATIVE SNAPSHOT" in mock_llm.calls[0]
    assert "Query: \"Analyze BTC right now\"" in mock_llm.calls[0]
    assert "LLM: BTC is showing strong continuous demand" in res.answer
    assert "Provider: test-llm (test-model)" in res.answer
    assert "DECISION SUPPORT ONLY" in res.disclaimer
    assert res.market_regime == "TRENDING_BULL"
    assert res.quant_score == 88.0