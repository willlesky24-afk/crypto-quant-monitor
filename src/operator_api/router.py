from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.operator_api.dependencies import (
    get_anomaly_detector,
    get_market_report_service,
    get_operator_assistant,
    get_operator_memory,
    get_operator_service,
    verify_security,
)
from src.operator_api.models import (
    CopilotQueryAPIResponse,
    CopilotQueryDTO,
    CopilotQueryRequest,
    DailyBriefingDTO,
    ExplanationDTO,
    HealthResponse,
    IntradayUpdateDTO,
    MarketAlertDTO,
    MarketSummaryAPIResponse,
    MarketSummaryDTO,
    ReadinessResponse,
    SignalExplanationAPIResponse,
    StatsResponse,
)
from src.operator_api.observability.metrics import get_metrics_collector
from src.operator_assistant.models import OperatorQuery
from src.operator_service.models import MarketSummaryRequest, SignalExplanationRequest
from src.operator_service.service import OperatorService

router = APIRouter(
    prefix="",
    tags=["Operator Intelligence"],
    dependencies=[Depends(verify_security)],
)



@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Operator Service Health Check",
    description="Returns operational status and active symbols tracked in the quantitative context provider.",
)
async def health_check(
    service: OperatorService = Depends(get_operator_service),
) -> HealthResponse:
    health = await service.health_check()
    return HealthResponse(
        status=health.status,
        available_symbols=health.available_symbols,
        timestamp=health.timestamp,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Operator Service Readiness Check",
    description="Verifies operational readiness of context storage and dependencies.",
)
async def readiness_check(
    service: OperatorService = Depends(get_operator_service),
) -> ReadinessResponse:
    provider = service.context_provider
    storage_healthy = True
    details: dict[str, Any] = {}
    tracked_symbols_count = 0
    total_records_count = 0

    try:
        symbols = await provider.get_available_symbols()
        tracked_symbols_count = len(symbols)
        details["available_symbols"] = symbols

        # Check repository if available (e.g. SQLiteMarketContextProvider)
        repo = getattr(provider, "repository", None)
        if repo is not None and hasattr(repo, "count_records"):
            total_records_count = repo.count_records()
            details["total_stored_records"] = total_records_count
        else:
            # In-memory or transient provider
            total_records_count = tracked_symbols_count
            details["provider_type"] = type(provider).__name__

        # Update metrics gauge
        collector = get_metrics_collector()
        collector.set_storage_metrics(
            records_count=total_records_count,
            active_symbols_count=tracked_symbols_count,
        )
    except Exception as exc:
        storage_healthy = False
        details["error"] = str(exc)

    status_str = "READY" if storage_healthy else "NOT_READY"
    status_code = status.HTTP_200_OK if storage_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    res = ReadinessResponse(
        status=status_str,
        storage_healthy=storage_healthy,
        tracked_symbols_count=tracked_symbols_count,
        total_records_count=total_records_count,
        details=details,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    if not storage_healthy:
        raise HTTPException(
            status_code=status_code,
            detail=res.model_dump(),
        )

    return res


@router.get(
    "/health/stats",
    response_model=StatsResponse,
    summary="Operator Service Statistics & Telemetry",
    description="Returns real-time operational telemetry, request counts, and latency statistics.",
)
async def service_stats(
    service: OperatorService = Depends(get_operator_service),
) -> StatsResponse:
    collector = get_metrics_collector()
    # Refresh storage gauges from active provider
    provider = service.context_provider
    try:
        symbols = await provider.get_available_symbols()
        repo = getattr(provider, "repository", None)
        records_count = repo.count_records() if repo is not None and hasattr(repo, "count_records") else len(symbols)
        collector.set_storage_metrics(records_count, len(symbols))
    except Exception:
        pass

    telemetry = collector.to_dict()
    telemetry["timestamp"] = datetime.now(timezone.utc).isoformat()
    return StatsResponse(**telemetry)


@router.get(
    "/metrics",
    summary="Prometheus Metrics Exposition",
    description="Returns API gateway operational metrics in Prometheus OpenMetrics text exposition format.",
)
async def prometheus_metrics(
    service: OperatorService = Depends(get_operator_service),
) -> Response:
    collector = get_metrics_collector()
    provider = service.context_provider
    try:
        symbols = await provider.get_available_symbols()
        repo = getattr(provider, "repository", None)
        records_count = repo.count_records() if repo is not None and hasattr(repo, "count_records") else len(symbols)
        collector.set_storage_metrics(records_count, len(symbols))
    except Exception:
        pass

    prometheus_data = collector.to_prometheus_text()
    return Response(content=prometheus_data, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get(
    "/signals/latest",
    response_model=SignalExplanationAPIResponse,
    summary="Get Latest Signal Explanation",
    description="Returns a human-readable, structured explanation for the latest closed candle signal.",
)
async def get_latest_signal_explanation(
    symbol: str = Query(..., description="Ticker symbol (e.g., BTCUSDT)"),
    timeframe: str = Query("1h", description="Candle interval (e.g., 1h)"),
    service: OperatorService = Depends(get_operator_service),
) -> SignalExplanationAPIResponse:
    req = SignalExplanationRequest(symbol=symbol, timeframe=timeframe)
    res = await service.get_signal_explanation(req)
    collector = get_metrics_collector()
    collector.record_explanation_request(success=res.success and res.explanation is not None)

    if not res.success or res.explanation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=res.error or f"No quantitative context found for {req.symbol} ({req.timeframe}).",
        )

    dto = ExplanationDTO(
        summary=res.explanation.summary,
        rationale=res.explanation.rationale,
        key_drivers=list(res.explanation.key_drivers),
        risk_assessment=res.explanation.risk_assessment,
        confidence=res.explanation.confidence,
        raw_response=res.explanation.raw_response,
        metadata=dict(res.explanation.metadata),
    )

    return SignalExplanationAPIResponse(
        success=True,
        symbol=res.symbol,
        timeframe=res.timeframe,
        explanation=dto,
        timestamp=res.timestamp,
    )


@router.get(
    "/market/summary",
    response_model=MarketSummaryAPIResponse,
    summary="Get Market Intelligence Summary",
    description="Returns an executive market briefing detailing regime, outlook, and key levels.",
)
async def get_market_summary(
    symbol: str = Query(..., description="Ticker symbol (e.g., BTCUSDT)"),
    timeframe: str = Query("1h", description="Candle interval (e.g., 1h)"),
    service: OperatorService = Depends(get_operator_service),
) -> MarketSummaryAPIResponse:
    req = MarketSummaryRequest(symbol=symbol, timeframe=timeframe)
    res = await service.get_market_summary(req)
    collector = get_metrics_collector()
    collector.record_summary_request(success=res.success and res.summary is not None)

    if not res.success or res.summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=res.error or f"No quantitative context found for {req.symbol} ({req.timeframe}).",
        )

    dto = MarketSummaryDTO(
        title=res.summary.title,
        overview=res.summary.overview,
        regime_interpretation=res.summary.regime_interpretation,
        outlook=res.summary.outlook,
        key_levels=dict(res.summary.key_levels),
        raw_response=res.summary.raw_response,
        metadata=dict(res.summary.metadata),
    )

    return MarketSummaryAPIResponse(
        success=True,
        symbol=res.symbol,
        timeframe=res.timeframe,
        summary=dto,
        timestamp=res.timestamp,
    )


@router.post(
    "/copilot/query",
    response_model=CopilotQueryAPIResponse,
    summary="Ask AI Quant Copilot",
    description="Processes natural operator inquiries and returns structured market interpretation and scenarios.",
)
async def ask_copilot(
    body: CopilotQueryRequest,
    assistant: Any = Depends(get_operator_assistant),
    memory: Any = Depends(get_operator_memory),
) -> CopilotQueryAPIResponse:
    query = OperatorQuery(
        query=body.query,
        symbol=body.symbol,
        timeframe=body.timeframe,
        operator_id=body.operator_id,
    )
    res = await assistant.ask(query)

    # Persist in memory
    try:
        await memory.add_entry(
            entry_type="query",
            symbol=res.symbol,
            content=f"Q: {body.query} | A: {res.answer[:200]}...",
            operator_id=body.operator_id,
        )
    except Exception:
        pass

    dto = CopilotQueryDTO(
        answer=res.answer,
        symbol=res.symbol,
        timeframe=res.timeframe,
        market_regime=res.market_regime,
        quant_score=res.quant_score,
        predictive_score=res.predictive_score,
        confidence=res.confidence,
        key_drivers=list(res.key_drivers),
        risk_factors=list(res.risk_factors),
        scenarios=list(res.scenarios),
        disclaimer=res.disclaimer,
    )
    return CopilotQueryAPIResponse(
        success=True,
        response=dto,
        timestamp=res.timestamp,
    )


@router.get(
    "/copilot/reports/daily",
    response_model=DailyBriefingDTO,
    summary="Get Daily Market Briefing",
    description="Returns an automated daily executive briefing generated from closed candle quantitative context.",
)
async def get_daily_briefing(
    symbol: str = Query(..., description="Ticker symbol (e.g., BTCUSDT)"),
    timeframe: str = Query("1h", description="Candle interval (e.g., 1h)"),
    service: OperatorService = Depends(get_operator_service),
    report_service: Any = Depends(get_market_report_service),
) -> DailyBriefingDTO:
    context = await service.context_provider.get_latest_context(symbol, timeframe)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No quantitative context available for {symbol} ({timeframe}).",
        )

    report = report_service.generate_daily_briefing(context)
    return DailyBriefingDTO(
        report_id=report.report_id,
        symbol=report.symbol,
        timeframe=report.timeframe,
        timestamp=report.timestamp,
        market_overview=report.market_overview,
        current_regime=report.current_regime,
        quant_score=report.quant_score,
        predictive_score=report.predictive_score,
        strongest_signals=list(report.strongest_signals),
        main_risks=list(report.main_risks),
        important_levels=dict(report.important_levels),
        volatility_analysis=report.volatility_analysis,
        historical_context=report.historical_context,
        disclaimer=report.disclaimer,
    )


@router.get(
    "/copilot/reports/intraday",
    response_model=IntradayUpdateDTO,
    summary="Get Intraday Delta Update",
    description="Returns an intraday delta report explaining price, score, and regime shifts.",
)
async def get_intraday_update(
    symbol: str = Query(..., description="Ticker symbol (e.g., BTCUSDT)"),
    timeframe: str = Query("1h", description="Candle interval (e.g., 1h)"),
    service: OperatorService = Depends(get_operator_service),
    report_service: Any = Depends(get_market_report_service),
) -> IntradayUpdateDTO:
    context = await service.context_provider.get_latest_context(symbol, timeframe)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No quantitative context available for {symbol} ({timeframe}).",
        )

    report = report_service.generate_intraday_update(context)
    return IntradayUpdateDTO(
        report_id=report.report_id,
        symbol=report.symbol,
        timeframe=report.timeframe,
        timestamp=report.timestamp,
        what_changed=report.what_changed,
        why_it_changed=report.why_it_changed,
        what_to_monitor=list(report.what_to_monitor),
        regime_shift=report.regime_shift,
        price_delta_pct=report.price_delta_pct,
        score_delta=report.score_delta,
        disclaimer=report.disclaimer,
    )


@router.get(
    "/copilot/anomalies",
    response_model=list[MarketAlertDTO],
    summary="Get Detected Market Anomalies",
    description="Returns recent passive market anomaly alerts (regime shifts, volatility expansion, score divergence).",
)
async def get_anomalies(
    symbol: str = Query(..., description="Ticker symbol (e.g., BTCUSDT)"),
    timeframe: str = Query("1h", description="Candle interval (e.g., 1h)"),
    service: OperatorService = Depends(get_operator_service),
    detector: Any = Depends(get_anomaly_detector),
) -> list[MarketAlertDTO]:
    context = await service.context_provider.get_latest_context(symbol, timeframe)
    if context is None:
        return []

    alerts = detector.evaluate(context)
    return [
        MarketAlertDTO(
            alert_id=a.alert_id,
            anomaly_type=a.anomaly_type.value,
            severity=a.severity.value,
            symbol=a.symbol,
            timeframe=a.timeframe,
            headline=a.headline,
            reason=a.reason,
            current_value=a.current_value,
            reference_value=a.reference_value,
            timestamp=a.timestamp,
            disclaimer=a.disclaimer,
        )
        for a in alerts
    ]


@router.get(
    "/copilot/memory",
    summary="Get Operator Memory Entries",
    description="Retrieves sanitized previous queries and notes recorded by the operator.",
)
async def get_memory_entries(
    symbol: str | None = Query(None, description="Optional symbol filter"),
    operator_id: str = Query("default_operator", description="Operator ID"),
    limit: int = Query(20, description="Max entries to return"),
    memory: Any = Depends(get_operator_memory),
) -> list[dict[str, Any]]:
    entries = await memory.get_recent_entries(
        symbol=symbol,
        operator_id=operator_id,
        limit=limit,
    )
    return [e.to_dict() for e in entries]

