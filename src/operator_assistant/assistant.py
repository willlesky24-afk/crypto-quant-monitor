from __future__ import annotations

import logging
import math

from src.ai_agent.interfaces import BaseAIProvider, MockAIProvider
from src.ai_agent.models import MarketContext
from src.ai_providers.interfaces import BaseLLMProvider
from src.ai_providers.prompt_builder import PromptBuilder
from src.operator_assistant.interfaces import BaseOperatorAssistant
from src.operator_assistant.models import (
    AnalysisRequest,
    AnalysisResponse,
    OperatorQuery,
    OperatorResponse,
)
from src.operator_assistant.on_demand_context import (
    build_on_demand_context,
    resolve_mentioned_symbol,
)
from src.operator_service.interfaces import BaseMarketContextProvider
from src.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class OperatorAssistant(BaseOperatorAssistant):
    """AI Quant Trading Copilot Assistant.

    Provides high-fidelity market intelligence and decision support directly to the human operator:
    - Interprets real-time quantitative context (QuantScore, PredictiveScore, MarketRegime, Risk).
    - Structures conditional scenario frameworks (Bullish continuation vs. Mean reversion).
    - Evaluates technical, volume profile, and risk indicators.
    - Zero execution authority: NEVER generates or executes automated trades.
    """

    def __init__(
        self,
        context_provider: BaseMarketContextProvider,
        ai_provider: BaseAIProvider | None = None,
        prompt_builder: PromptBuilder | None = None,
        enable_on_demand_context: bool = True,
    ) -> None:
        self._context_provider = context_provider
        self._ai_provider = ai_provider or MockAIProvider()
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._enable_on_demand_context = enable_on_demand_context

    @property
    def context_provider(self) -> BaseMarketContextProvider:
        return self._context_provider

    @property
    def ai_provider(self) -> BaseAIProvider:
        return self._ai_provider

    @property
    def prompt_builder(self) -> PromptBuilder:
        return self._prompt_builder

    @staticmethod
    def _validated_risk_plan(context: MarketContext) -> dict:
        """Use effective levels from RiskEngine; never infer an activation or fill."""
        meta = context.metadata
        entry = meta["entry_price"] if "entry_price" in meta else context.current_price
        levels = RiskEngine().calculate_levels(
            entry, context.risk.stop_loss, context.risk.take_profit, context.signal.direction
        )
        status = meta.get("signal_status", "SIN CONFIRMACIÓN")
        reason = levels["reason"]
        if status in {"NO DISPONIBLE", "DESCARTADA", "ESPERANDO CONFIRMACIÓN"}:
            reason = meta.get("risk_reason") or "No existe un plan de riesgo activo."
        if reason is None:
            for reported in (context.risk.risk_ratio, meta.get("risk_reward_ratio")):
                if reported is None:
                    continue
                try:
                    value = float(reported)
                except (TypeError, ValueError, OverflowError):
                    value = math.nan
                if not math.isfinite(value) or not math.isclose(
                    value, levels["gross_risk_reward"], rel_tol=1e-6, abs_tol=0.005
                ):
                    reason = "R:R informado no coincide con los niveles efectivos."
                    break
        if reason is not None:
            return {
                "status": status if status in {"ESPERANDO CONFIRMACIÓN", "DESCARTADA"} else "NO DISPONIBLE",
                "reason": reason, "entry_price": None,
                "stop_loss": None, "take_profit": None, "gross_risk_reward": None,
                "entry_confirmed": False,
            }
        return {
            **levels,
            "status": status,
            "entry_confirmed": status == "ACTIVADA" and meta.get("entry_confirmed") is True,
        }


    def _extract_symbol_timeframe(self, text: str, fallback_symbol: str, fallback_tf: str) -> tuple[str, str]:
        """Extract symbol and timeframe tokens if explicitly mentioned in query string."""
        sym, tf, _ = resolve_mentioned_symbol(text, fallback_symbol, fallback_tf)
        return sym, tf

    async def ask(self, query: OperatorQuery) -> OperatorResponse:
        """Process an operator query and return structured market interpretation and decision support."""
        symbol, timeframe, is_fx = resolve_mentioned_symbol(
            query.query, query.symbol, query.timeframe
        )

        context = await self._context_provider.get_latest_context(symbol, timeframe)
        if context is None and self._enable_on_demand_context:
            # Build on-demand live context dynamically
            context = build_on_demand_context(symbol, timeframe, is_fx)
            if context is not None:
                try:
                    await self._context_provider.update_context(context)
                except Exception:
                    pass

        if context is None:
            return OperatorResponse(
                answer=(
                    f"Unable to analyze {symbol} ({timeframe}): No closed-candle quantitative "
                    f"context is currently available in the active provider."
                ),
                symbol=symbol,
                timeframe=timeframe,
                market_regime="UNKNOWN",
                quant_score=0.0,
                predictive_score=0.0,
                confidence=0.0,
                key_drivers=(),
                risk_factors=("Context unavailable",),
                scenarios=(),
            )

        images_list = query.metadata.get("images") if query.metadata else None
        num_images = (
            len(images_list)
            if images_list
            else (1 if bool(query.metadata and query.metadata.get("image_bytes")) else 0)
        )
        has_image = num_images > 0

        # Delegate narrative generation to AI provider
        if isinstance(self._ai_provider, BaseLLMProvider):
            prompt = self._prompt_builder.build_copilot_prompt(
                context=context,
                query=query.query,
                has_image=has_image,
                num_images=num_images,
            )
            llm_res = await self._ai_provider.generate_response(prompt, metadata=query.metadata)
            if llm_res.content.startswith("⚠️") or "fallback" in llm_res.provider:
                if has_image:
                    image_noun = "las imágenes" if num_images > 1 else "la imagen"
                    explanation_summary = (
                        f"{llm_res.content}\n\n"
                        f"⚠️ *Nota: No fue posible procesar {image_noun} con el servicio multimodal en este intento. "
                        f"Por favor verifica la clave de Gemini o reintenta subir el gráfico.*"
                    )
                else:
                    local_explanation = self._generate_local_explanation_es(context, query.query)
                    explanation_summary = f"{llm_res.content}\n\n{local_explanation}"
            else:
                explanation_summary = llm_res.content
            market_outlook = f"Provider: {llm_res.provider} ({llm_res.model}) | Latencia: {llm_res.latency_ms:.1f}ms"
            key_drivers = list(context.signal.positives) or [
                f"Régimen: {context.market_regime}",
                f"Puntuación Quant: {context.quant_score:.1f}",
            ]
        else:
            explanation = await self._ai_provider.generate_explanation(context)
            summary = await self._ai_provider.summarize_market(context)
            explanation_summary = explanation.summary
            market_outlook = summary.outlook
            key_drivers = list(explanation.key_drivers) if explanation.key_drivers else list(context.signal.positives)
            if not key_drivers:
                key_drivers.append(f"Regime: {context.market_regime}")
                key_drivers.append(f"Quant Score: {context.quant_score:.1f}")

        # Build scenario matrix based on quantitative and predictive metrics
        plan = self._validated_risk_plan(context)
        scenarios = self._formulate_scenarios(context)
        risk_factors = list(context.signal.warnings)
        if context.risk.risk_category:
            risk_factors.append(f"Risk Category: {context.risk.risk_category}")

        answer = self._compose_copilot_narrative(
            query=query.query,
            context=context,
            explanation_summary=explanation_summary,
            market_outlook=market_outlook,
            scenarios=scenarios,
            has_image=has_image,
            num_images=num_images,
        )

        return OperatorResponse(

            answer=answer,
            symbol=context.symbol,
            timeframe=context.timeframe,
            market_regime=context.market_regime,
            quant_score=context.quant_score,
            predictive_score=context.predictive_score,
            confidence=context.signal.confidence,
            key_drivers=tuple(key_drivers),
            risk_factors=tuple(risk_factors),
            scenarios=tuple(scenarios),
            metadata={
                "current_price": context.current_price,
                "action_bias": context.signal.action,
                "direction_bias": context.signal.direction,
                "signal_status": plan["status"],
                "entry_confirmed": plan["entry_confirmed"],
                "entry_price": plan["entry_price"],
                "stop_loss": plan["stop_loss"],
                "take_profit": plan["take_profit"],
                "gross_risk_reward": plan["gross_risk_reward"],
                "risk_reason": plan["reason"],
            },
        )

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Perform a deep-dive contextual breakdown for the requested asset."""
        context = await self._context_provider.get_latest_context(
            request.symbol, request.timeframe
        )

        if context is None:
            return AnalysisResponse(
                symbol=request.symbol,
                timeframe=request.timeframe,
                current_price=0.0,
                market_regime="UNKNOWN",
                quant_score=0.0,
                predictive_score=0.0,
                technical_summary=f"No data available for {request.symbol} ({request.timeframe}).",
                volume_analysis="No volume profile data available.",
                risk_assessment="No risk boundaries calculated.",
                possible_scenarios=(),
            )

        scenarios = self._formulate_scenarios(context)

        # Technical Indicators overview
        tech_lines: list[str] = []
        for k, v in sorted(context.technical_indicators.items()):
            val_str = f"{v:.2f}" if isinstance(v, float) else str(v)
            tech_lines.append(f"- {k}: {val_str}")
        tech_summary = "\n".join(tech_lines) if tech_lines else "Indicators within expected baselines."

        # Volume Profile summary
        vp = context.volume_profile
        poc = vp.get("poc", "N/A")
        vah = vp.get("vah", "N/A")
        val = vp.get("val", "N/A")
        vol_summary = f"POC: {poc} | Value Area High (VAH): {vah} | Value Area Low (VAL): {val}"

        # Risk parameters
        plan = self._validated_risk_plan(context)
        risk_summary = (
            f"Estado: {plan['status']} | Entrada: {plan['entry_price'] if plan['entry_price'] is not None else 'N/A'} | "
            f"Stop Loss: {plan['stop_loss'] if plan['stop_loss'] is not None else 'N/A'} | "
            f"Take Profit: {plan['take_profit'] if plan['take_profit'] is not None else 'N/A'} | "
            f"R bruto: {plan['gross_risk_reward'] if plan['gross_risk_reward'] is not None else 'N/A'} | "
            f"Motivo: {plan['reason'] or 'Ninguno'}"
        )

        return AnalysisResponse(
            symbol=context.symbol,
            timeframe=context.timeframe,
            current_price=context.current_price,
            market_regime=context.market_regime,
            quant_score=context.quant_score,
            predictive_score=context.predictive_score,
            technical_summary=tech_summary,
            volume_analysis=vol_summary,
            risk_assessment=risk_summary,
            possible_scenarios=tuple(scenarios),
        )

    def _generate_local_explanation_es(self, context: MarketContext, query: str) -> str:
        """Generate high-fidelity everyday Spanish explanation when remote LLM is in fallback mode."""
        regime = context.market_regime
        if "BULL" in regime:
            regime_desc = "Tendencia Alcista (compradores al mando del mercado)"
        elif "BEAR" in regime:
            regime_desc = "Tendencia Bajista (vendedores con mayor presión)"
        elif "RANGE" in regime or "CONSOLIDATION" in regime or "CHOPPY" in regime:
            regime_desc = "Rango o Consolidación (mercado lateral buscando liquidez)"
        else:
            regime_desc = f"Régimen de Mercado {regime}"

        direction_desc = (
            "al alza (compra / LONG)"
            if context.signal.direction == "LONG"
            else ("a la baja (venta / SHORT)" if context.signal.direction == "SHORT" else "neutral / a la espera")
        )

        quant_fuerza = (
            "muy alta" if context.quant_score >= 80 else ("moderada-alta" if context.quant_score >= 65 else "neutral/precaución")
        )

        poc_val = context.volume_profile.get("poc") if context.volume_profile else None
        poc_text = (
            f"El nivel de mayor acumulación de volumen institucional (POC) se ubica en **${poc_val:,.2f}**."
            if poc_val
            else "El perfil de volumen institucional no define una concentración anómala."
        )

        plan = self._validated_risk_plan(context)
        sl = plan["stop_loss"]
        tp = plan["take_profit"]
        sl_text = f"${sl:,.2f}" if sl is not None else "N/A"
        tp_text = f"${tp:,.2f}" if tp is not None else "N/A"

        lines = [
            f"📊 **Diagnóstico Cuantitativo en Lenguaje Cotidiano para {context.symbol} ({context.timeframe.upper()}):**",
            f"- **Postura y Dirección:** El sistema sugiere `{context.signal.action}` {direction_desc}.",
            f"- **Régimen de Mercado:** Actualmente en **{regime_desc}** con el precio en **${context.current_price:,.2f}**.",
            f"- **Fuerza Técnica (Quant Score):** **{context.quant_score:.1f}/100** (fuerza {quant_fuerza}). De cada 10 métricas analizadas, aproximadamente **{int(context.quant_score/10)} respaldan** este diagnóstico.",
            f"- **Probabilidad Predictiva:** **{context.predictive_score:.2f}** con una confianza estadística del **{context.signal.confidence * 100:.1f}%**.",
            f"- **Nivel Clave Institucional:** {poc_text}",
            f"- **Plan de riesgo ({plan['status']}):** Stop Loss **{sl_text}**; Take Profit **{tp_text}**. {plan['reason'] or 'Niveles validados; entrada no confirmada salvo estado ACTIVADA.'}",
        ]

        if context.signal.positives:
            lines.append(f"- **Factores a Favor:** {', '.join(context.signal.positives)}.")

        return "\n".join(lines)

    def _formulate_scenarios(self, context: MarketContext) -> list[str]:
        """Formulate scenario frameworks based on quantitative indicators."""
        scenarios: list[str] = []
        regime = context.market_regime
        pred = context.predictive_score
        quant = context.quant_score

        if "BULL" in regime or pred > 0.65:
            plan = self._validated_risk_plan(context)
            support = (
                f"SL técnico indicativo {plan['stop_loss']}"
                if plan["stop_loss"] is not None else "soporte aún no validado"
            )
            scenarios.append(
                f"Escenario Principal (Bullish Expansion / Expansión Alcista): Continuación hacia resistencia manteniendo soporte "
                f"en {support}."
            )
            scenarios.append(
                "Escenario Alternativo (Exhaustion / Agotamiento): Pérdida de impulso podría provocar "
                "un retroceso hacia el punto de control institucional (POC)."
            )
        elif "BEAR" in regime or pred < 0.35:
            scenarios.append(
                f"Escenario Principal (Bearish Continuation / Continuación Bajista): Presión a la baja favorecida bajo régimen {regime}; "
                f"vigilar posible ruptura de soporte clave."
            )
            scenarios.append(
                "Escenario Alternativo (Short Squeeze / Rebote Técnico): Una divergencia alcista podría provocar "
                "una recuperación rápida de liquidez hacia la parte alta del perfil (VAH)."
            )
        else:
            scenarios.append(
                f"Escenario Principal (Range Bound / Rango Lateral): Oscilación de precio dentro del área de valor "
                f"con Puntuación Quant en {quant:.1f}/100."
            )
            scenarios.append(
                "Escenario de Ruptura (Breakout): Se requiere volumen institucional significativo para validar una salida de rango."
            )

        return scenarios

    def _compose_copilot_narrative(
        self,
        query: str,
        context: MarketContext,
        explanation_summary: str,
        market_outlook: str,
        scenarios: list[str],
        has_image: bool = False,
        num_images: int = 1,
    ) -> str:
        """Assemble structured markdown narrative for the human operator."""
        if has_image:
            header = (
                f"### 🤖 Copilot Intelligence — Análisis Visual de Gráficos / Señales Adjuntas ({num_images} imágenes)"
                if num_images > 1
                else "### 🤖 Copilot Intelligence — Análisis Visual de Gráfico / Señal Adjunta"
            )
            lines = [
                header,
                "",
                "**Observaciones visuales generadas por IA: no son niveles verificados ni entradas operativas.**",
                explanation_summary,
                "",
                f"*{market_outlook}*",
            ]
            plan = self._validated_risk_plan(context)
            lines.extend(self._format_risk_plan(plan, context.symbol))
            return "\n".join(lines)

        lines = [
            f"### 🤖 Copilot Intelligence (Diagnóstico Cuantitativo): {context.symbol} [{context.timeframe.upper()}]",
            f"**Precio Actual:** ${context.current_price:,.2f} | **Régimen de Mercado:** `{context.market_regime}`",
            f"**Puntuación Quant:** {context.quant_score:.1f}/100 | **Puntaje Predictivo:** {context.predictive_score:.2f} | **Confianza:** {context.signal.confidence*100:.1f}%",
            "",
            "#### 📊 Interpretación descriptiva de IA (no modifica el estado de señal)",
            f"{explanation_summary}",
            f"{market_outlook}",
            "",
            "#### 🎯 Escenarios para Evaluación del Operador (Scenarios)",
        ]
        for sc in scenarios:
            lines.append(f"- {sc}")

        plan = self._validated_risk_plan(context)
        lines.extend(self._format_risk_plan(plan, context.symbol))

        if context.signal.warnings:
            lines.append("- **Advertencias Activas:**")
            for w in context.signal.warnings:
                lines.append(f"  * ⚠️ {w}")

        lines.append("")
        lines.extend(self._build_conclusive_verdict(context, plan))

        return "\n".join(lines)

    @staticmethod
    def _format_risk_plan(plan: dict, symbol: str) -> list[str]:
        """Render only levels validated by RiskEngine, never image or AI estimates."""
        is_fx = "=X" in symbol

        def fmt(value: float | None) -> str:
            if value is None:
                return "N/A"
            return f"${value:,.4f}" if is_fx or value < 10 else f"${value:,.2f}"

        lines = [
            "",
            "#### 🛡️ Parámetros de Riesgo Sugeridos — contrato RiskEngine",
            f"- **Estado:** {plan['status']}",
            f"- **Entrada propuesta:** {fmt(plan['entry_price'])}",
            f"- **Stop Loss (Corte de pérdida):** {fmt(plan['stop_loss'])}",
            f"- **Take Profit (Toma de beneficio):** {fmt(plan['take_profit'])}",
        ]
        if plan["gross_risk_reward"] is None:
            lines.append("- **R bruto:** N/A")
            lines.append(f"- **Motivo:** {plan['reason'] or 'Sin niveles validados.'}")
        else:
            lines.append(f"- **R bruto sin costes:** 1:{plan['gross_risk_reward']:.2f}")
            if not plan["entry_confirmed"]:
                lines.append("- **Entrada no confirmada:** escenario técnico, no señal activada.")
        return lines

    @staticmethod
    def _build_conclusive_verdict(context: MarketContext, plan: dict) -> list[str]:
        """Keep descriptive market bias separate from operational activation."""
        direction = context.signal.direction
        if plan["status"] == "ACTIVADA" and plan["entry_confirmed"]:
            verdict = (
                f"Estado ACTIVADA para {direction}; los niveles indicados arriba fueron "
                "validados por RiskEngine. La ejecución real y los costes no se infieren."
            )
        elif plan["gross_risk_reward"] is not None:
            verdict = (
                f"En Espera / Precaución (NO entrar ahora): sesgo técnico {direction}, "
                f"estado {plan['status']}. La entrada propuesta no está confirmada."
            )
        else:
            verdict = (
                "En Espera / Precaución (NO entrar ahora): no existe un plan de riesgo "
                f"validado. {plan['reason'] or 'Datos insuficientes.'}"
            )
        return [
            "---",
            "### 🏁 Conclusión Operativa y Veredicto Técnico:",
            f"* **Respuesta técnica**: {verdict}",
        ]
