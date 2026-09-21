from __future__ import annotations

from abc import ABC, abstractmethod

from src.operator_assistant.models import (
    AnalysisRequest,
    AnalysisResponse,
    OperatorQuery,
    OperatorResponse,
)


class BaseOperatorAssistant(ABC):
    """Abstract interface defining the contract for the AI Quant Trading Copilot.

    The Copilot serves as an interactive decision-support layer for the human operator.
    It explains market context, structures scenarios, and surfaces risks, but never
    executes orders, issues automated buy/sell mandates, or modifies quantitative engines.
    """

    @abstractmethod
    async def ask(self, query: OperatorQuery) -> OperatorResponse:
        """Process a natural language or structured question from the operator."""
        ...

    @abstractmethod
    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Perform a deep-dive contextual analysis for a designated symbol and timeframe."""
        ...