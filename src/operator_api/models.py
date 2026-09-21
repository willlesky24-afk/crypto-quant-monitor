from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """API response model for service health and tracked symbols."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="Operational status of the API gateway")
    available_symbols: list[str] = Field(default_factory=list, description="Symbols with active context")
    timestamp: str = Field(..., description="UTC ISO timestamp of the response")


class ExplanationDTO(BaseModel):
    """External Data Transfer Object representing an AI-generated signal explanation."""

    model_config = ConfigDict(frozen=True)

    summary: str = Field(..., description="Executive narrative summary of the setup")
    rationale: str = Field(..., description="Detailed quantitative rationale")
    key_drivers: list[str] = Field(default_factory=list, description="Primary positive or negative factors")
    risk_assessment: str = Field(..., description="Risk boundaries, SL, TP, and R:R evaluation")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    raw_response: str = Field(default="", description="Raw LLM/template output string")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual tracking metadata")


class SignalExplanationAPIResponse(BaseModel):
    """API response model for GET /signals/latest."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Indicates if the explanation was generated")
    symbol: str = Field(..., description="Market ticker symbol (e.g., BTCUSDT)")
    timeframe: str = Field(..., description="Candle interval (e.g., 1h)")
    explanation: ExplanationDTO = Field(..., description="Structured explanation object")
    timestamp: str = Field(..., description="UTC ISO timestamp")


class MarketSummaryDTO(BaseModel):
    """External Data Transfer Object representing a market intelligence summary."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(..., description="Title of the briefing")
    overview: str = Field(..., description="Executive market overview")
    regime_interpretation: str = Field(..., description="Structural regime and volume profile context")
    outlook: str = Field(..., description="Operational outlook and risk environment")
    key_levels: dict[str, float] = Field(default_factory=dict, description="Key price, POC, VAH, VAL, and risk levels")
    raw_response: str = Field(default="", description="Raw LLM/template output string")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual tracking metadata")


class MarketSummaryAPIResponse(BaseModel):
    """API response model for GET /market/summary."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Indicates if the summary was generated")
    symbol: str = Field(..., description="Market ticker symbol (e.g., BTCUSDT)")
    timeframe: str = Field(..., description="Candle interval (e.g., 1h)")
    summary: MarketSummaryDTO = Field(..., description="Structured summary object")
    timestamp: str = Field(..., description="UTC ISO timestamp")


class ReadinessResponse(BaseModel):
    """API response model for GET /health/ready."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="Overall readiness status ('READY' or 'NOT_READY')")
    storage_healthy: bool = Field(..., description="Indicates if context storage is accessible")
    tracked_symbols_count: int = Field(..., description="Number of active symbols in storage")
    total_records_count: int = Field(..., description="Total context snapshots stored")
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic details")
    timestamp: str = Field(..., description="UTC ISO timestamp")


class StatsResponse(BaseModel):
    """API response model for GET /health/stats."""

    model_config = ConfigDict(frozen=True)

    http_requests_total: int = Field(..., description="Total HTTP requests received")
    http_requests_active: int = Field(..., description="In-flight active requests")
    rate_limit_rejections_total: int = Field(..., description="Rate limit rejections count")
    explanation_requests_total: int = Field(..., description="Total signal explanation requests")
    explanation_errors_total: int = Field(..., description="Explanation errors count")
    summary_requests_total: int = Field(..., description="Total market summary requests")
    summary_errors_total: int = Field(..., description="Summary errors count")
    bridge_events_processed_total: int = Field(..., description="Bridge events processed")
    stored_records_count: int = Field(..., description="Context records count in storage")
    active_symbols_count: int = Field(..., description="Active symbols count")
    latency_stats: dict[str, float] = Field(..., description="Latency statistics in ms")
    requests_by_route: list[dict[str, Any]] = Field(default_factory=list, description="Request breakdown")
    timestamp: str = Field(..., description="UTC ISO timestamp")


class CopilotQueryRequest(BaseModel):
    """API request model for POST /copilot/query."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(..., description="Natural language question or command from the operator")
    symbol: str = Field(default="BTCUSDT", description="Target market symbol")
    timeframe: str = Field(default="1h", description="Candle interval")
    operator_id: str = Field(default="default_operator", description="Identifier of the operator")


class CopilotQueryDTO(BaseModel):
    """External DTO representing a structured AI Copilot answer."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(..., description="Markdown formatted analytical answer")
    symbol: str = Field(..., description="Target market symbol")
    timeframe: str = Field(..., description="Candle interval")
    market_regime: str = Field(..., description="Market regime classification")
    quant_score: float = Field(..., description="Quant score (0-100)")
    predictive_score: float = Field(..., description="Predictive score (0-1.0)")
    confidence: float = Field(..., description="Signal confidence")
    key_drivers: list[str] = Field(default_factory=list, description="Primary drivers")
    risk_factors: list[str] = Field(default_factory=list, description="Identified risk factors")
    scenarios: list[str] = Field(default_factory=list, description="Possible scenario frameworks")
    disclaimer: str = Field(..., description="Decision support disclaimer")


class CopilotQueryAPIResponse(BaseModel):
    """API response model for POST /copilot/query."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Whether query was answered")
    response: CopilotQueryDTO = Field(..., description="Structured Copilot response")
    timestamp: str = Field(..., description="UTC ISO timestamp")


class DailyBriefingDTO(BaseModel):
    """External DTO for Daily Briefing Report."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    symbol: str
    timeframe: str
    timestamp: str
    market_overview: str
    current_regime: str
    quant_score: float
    predictive_score: float
    strongest_signals: list[str]
    main_risks: list[str]
    important_levels: dict[str, Any]
    volatility_analysis: str
    historical_context: str
    disclaimer: str


class IntradayUpdateDTO(BaseModel):
    """External DTO for Intraday Update Report."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    symbol: str
    timeframe: str
    timestamp: str
    what_changed: str
    why_it_changed: str
    what_to_monitor: list[str]
    regime_shift: str | None = None
    price_delta_pct: float = 0.0
    score_delta: float = 0.0
    disclaimer: str


class MarketAlertDTO(BaseModel):
    """External DTO for detected Market Anomaly."""

    model_config = ConfigDict(frozen=True)

    alert_id: str
    anomaly_type: str
    severity: str
    symbol: str
    timeframe: str
    headline: str
    reason: str
    current_value: float
    reference_value: float
    timestamp: str
    disclaimer: str

