from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from src.ai_agent.models import AgentExplanation, AgentMarketSummary, MarketContext
from src.ai_providers.interfaces import BaseLLMProvider
from src.ai_providers.models import AIResponse

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Local Ollama LLM provider for secure, on-premise execution.

    Connects to local Ollama daemon (default: http://localhost:11434).
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 1,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def generate_response(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> AIResponse:
        t0 = time.perf_counter()
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    text = resp_data.get("response", "")
                    tokens = resp_data.get("eval_count")
                    latency = (time.perf_counter() - t0) * 1000.0
                    return AIResponse(
                        content=text or "No response from local Ollama model.",
                        provider="ollama",
                        model=self.model,
                        latency_ms=round(latency, 2),
                        tokens_used=tokens,
                        metadata=metadata or {},
                    )
            except Exception as exc:
                logger.warning(f"Ollama API attempt {attempt+1} failed: {exc}")
                if attempt < self.max_retries:
                    time.sleep(0.5)
                else:
                    return self._fallback_response(
                        f"Local Ollama daemon unreachable at {self.base_url} ({exc}).",
                        t0,
                    )


    def _fallback_response(self, reason: str, start_time: float) -> AIResponse:
        latency = (time.perf_counter() - start_time) * 1000.0
        return AIResponse(
            content=f"⚠️ {reason}",
            provider="ollama-fallback",
            model=self.model,
            latency_ms=round(latency, 2),
            tokens_used=0,
            metadata={"status": "fallback"},
        )

    async def generate_explanation(self, context: MarketContext) -> AgentExplanation:
        prompt = (
            f"Explain quantitative signal for {context.symbol} ({context.timeframe}).\n"
            f"Regime: {context.market_regime}, Quant Score: {context.quant_score:.1f}, "
            f"Predictive Score: {context.predictive_score:.2f}, Action: {context.signal.action}"
        )
        res = await self.generate_response(prompt)
        return AgentExplanation(
            summary=res.content[:200],
            rationale=res.content,
            key_drivers=context.signal.positives or (f"Regime: {context.market_regime}",),
            risk_assessment=f"SL: {context.risk.stop_loss} | TP: {context.risk.take_profit}",
            confidence=context.signal.confidence,
            raw_response=res.content,
        )

    async def summarize_market(self, context: MarketContext) -> AgentMarketSummary:
        prompt = f"Summarize market for {context.symbol} in regime {context.market_regime}."
        res = await self.generate_response(prompt)
        return AgentMarketSummary(
            title=f"Ollama Local Briefing: {context.symbol}",
            overview=res.content[:250],
            regime_interpretation=f"Current regime is {context.market_regime}.",
            outlook="Local quantitative review.",
            key_levels={"Price": context.current_price},
            raw_response=res.content,
        )

    async def health_check(self) -> bool:
        return True