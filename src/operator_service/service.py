from __future__ import annotations

from src.ai_agent.explanation import SignalExplanationService
from src.ai_agent.reporting import MarketReportGenerator
from src.operator_service.interfaces import (
    BaseMarketContextProvider,
    BaseOperatorService,
)
from src.operator_service.models import (
    MarketSummaryRequest,
    MarketSummaryResponse,
    OperatorServiceHealthResponse,
    SignalExplanationRequest,
    SignalExplanationResponse,
)


class OperatorService(BaseOperatorService):
    """Independent read-only service exposing AI interpretation capabilities to external clients.

    Strictly complies with the architectural constraints:
    - READ-ONLY: Never generates trading signals, executes trades, or modifies decisions.
    - Consumes existing quantitative snapshots via BaseMarketContextProvider.
    - Delegates explanation to SignalExplanationService and summaries to MarketReportGenerator.
    - Fully async-compatible for future API, Telegram, web, or mobile integrations.
    """

    def __init__(
        self,
        context_provider: BaseMarketContextProvider,
        explanation_service: SignalExplanationService | None = None,
        report_generator: MarketReportGenerator | None = None,
    ) -> None:
        """Initialize the operator service.

        Args:
            context_provider: Source of existing quantitative MarketContext snapshots.
            explanation_service: Optional custom explanation service (defaults to deterministic).
            report_generator: Optional custom report generator (defaults to deterministic).
        """
        self._context_provider = context_provider
        self._explanation_service = explanation_service or SignalExplanationService()
        self._report_generator = report_generator or MarketReportGenerator()

    @property
    def context_provider(self) -> BaseMarketContextProvider:
        """Access the underlying context provider."""
        return self._context_provider

    async def get_signal_explanation(
        self, request: SignalExplanationRequest
    ) -> SignalExplanationResponse:
        """Retrieve a structured explanation for the latest quantitative signal.

        Args:
            request: Structured request specifying symbol and timeframe.

        Returns:
            SignalExplanationResponse containing explanation if found, or error description.
        """
        context = await self._context_provider.get_latest_context(
            request.symbol, request.timeframe
        )
        if context is None:
            return SignalExplanationResponse(
                success=False,
                symbol=request.symbol,
                timeframe=request.timeframe,
                explanation=None,
                error=f"No quantitative context found for {request.symbol} ({request.timeframe}).",
            )

        explanation = await self._explanation_service.explain_async(context)
        return SignalExplanationResponse(
            success=True,
            symbol=request.symbol,
            timeframe=request.timeframe,
            explanation=explanation,
            error=None,
        )

    async def get_market_summary(
        self, request: MarketSummaryRequest
    ) -> MarketSummaryResponse:
        """Retrieve a structured market intelligence briefing.

        Args:
            request: Structured request specifying symbol and timeframe.

        Returns:
            MarketSummaryResponse containing summary if found, or error description.
        """
        context = await self._context_provider.get_latest_context(
            request.symbol, request.timeframe
        )
        if context is None:
            return MarketSummaryResponse(
                success=False,
                symbol=request.symbol,
                timeframe=request.timeframe,
                summary=None,
                error=f"No quantitative context found for {request.symbol} ({request.timeframe}).",
            )

        summary = await self._report_generator.generate_report_async(context)
        return MarketSummaryResponse(
            success=True,
            symbol=request.symbol,
            timeframe=request.timeframe,
            summary=summary,
            error=None,
        )

    async def health_check(self) -> OperatorServiceHealthResponse:
        """Check operational readiness and return tracked symbols."""
        symbols = await self._context_provider.get_available_symbols()
        return OperatorServiceHealthResponse(
            status="HEALTHY",
            available_symbols=symbols,
        )
