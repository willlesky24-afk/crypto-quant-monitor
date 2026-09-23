from __future__ import annotations

import logging

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

        # Delegate narrative generation to AI provider
        if isinstance(self._ai_provider, BaseLLMProvider):
            prompt = self._prompt_builder.build_copilot_prompt(
                context=context,
                query=query.query,
            )
            llm_res = await self._ai_provider.generate_response(prompt, metadata=query.metadata)
            if llm_res.content.startswith("⚠️") or "fallback" in llm_res.provider:
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
                "stop_loss": context.risk.stop_loss,
                "take_profit": context.risk.take_profit,
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
        risk_summary = (
            f"Category: {context.risk.risk_category or 'Moderate'} | "
            f"Stop Loss: {context.risk.stop_loss or 'N/A'} | "
            f"Take Profit: {context.risk.take_profit or 'N/A'} | "
            f"ATR: {context.risk.atr or 'N/A'}"
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

        sl = context.risk.stop_loss
        tp = context.risk.take_profit
        sl_text = f"${sl:,.2f}" if sl else "dinámico por volatilidad"
        tp_text = f"${tp:,.2f}" if tp else "dinámico por volatilidad"

        lines = [
            f"📊 **Diagnóstico Cuantitativo en Lenguaje Cotidiano para {context.symbol} ({context.timeframe.upper()}):**",
            f"- **Postura y Dirección:** El sistema sugiere `{context.signal.action}` {direction_desc}.",
            f"- **Régimen de Mercado:** Actualmente en **{regime_desc}** con el precio en **${context.current_price:,.2f}**.",
            f"- **Fuerza Técnica (Quant Score):** **{context.quant_score:.1f}/100** (fuerza {quant_fuerza}). De cada 10 métricas analizadas, aproximadamente **{int(context.quant_score/10)} respaldan** este diagnóstico.",
            f"- **Probabilidad Predictiva:** **{context.predictive_score:.2f}** con una confianza estadística del **{context.signal.confidence * 100:.1f}%**.",
            f"- **Nivel Clave Institucional:** {poc_text}",
            f"- **Parámetros de Seguridad:** Corte de riesgo (Stop Loss) recomendado en **{sl_text}** y objetivo (Take Profit) en **{tp_text}**.",
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
            scenarios.append(
                f"Escenario Principal (Bullish Expansion / Expansión Alcista): Continuación hacia resistencia manteniendo soporte "
                f"en nivel de Stop Loss ({context.risk.stop_loss or 'pivote cercano'})."
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
    ) -> str:
        """Assemble structured markdown narrative for the human operator."""
        lines = [
            f"### 🤖 Copilot Intelligence (Diagnóstico Cuantitativo): {context.symbol} [{context.timeframe.upper()}]",
            f"**Precio Actual:** ${context.current_price:,.2f} | **Régimen de Mercado:** `{context.market_regime}`",
            f"**Puntuación Quant:** {context.quant_score:.1f}/100 | **Puntaje Predictivo:** {context.predictive_score:.2f} | **Confianza:** {context.signal.confidence*100:.1f}%",
            "",
            "#### 📊 Evaluación Cuantitativa y Diagnóstico (Quantitative Assessment)",
            f"{explanation_summary}",
            f"{market_outlook}",
            "",
            "#### 🎯 Escenarios para Evaluación del Operador (Scenarios)",
        ]
        for sc in scenarios:
            lines.append(f"- {sc}")

        price = context.current_price
        is_fx = "=X" in context.symbol or price < 10

        def _fmt(val: float | None) -> str:
            if val is None:
                return "N/A"
            if is_fx or val < 10:
                return f"${val:,.4f}"
            return f"${val:,.2f}"

        atr = context.risk.atr or (price * 0.003 if is_fx else price * 0.015)
        direction = (context.signal.direction or "").upper()
        action = (context.signal.action or "").upper()

        sl = context.risk.stop_loss
        tp = context.risk.take_profit
        if sl is None and price > 0:
            if "SHORT" in direction or "SELL" in action:
                sl = price + 1.5 * atr
            else:
                sl = max(0.0, price - 1.5 * atr)

        if tp is None and price > 0:
            if "SHORT" in direction or "SELL" in action:
                tp = max(0.0, price - 3.0 * atr)
            else:
                tp = price + 3.0 * atr

        sl_str = _fmt(sl)
        tp_str = _fmt(tp)

        lines.extend([
            "",
            "#### 🛡️ Parámetros de Riesgo y Protección (Risk & Boundaries)",
            f"- **Nivel de Stop Loss (Corte de Riesgo):** {sl_str}",
            f"- **Objetivo de Take Profit (Toma de Ganancias):** {tp_str}",
            f"- **Categoría de Riesgo:** {context.risk.risk_category or 'Estándar'}",
        ])

        if context.signal.warnings:
            lines.append("- **Advertencias Activas:**")
            for w in context.signal.warnings:
                lines.append(f"  * ⚠️ {w}")

        lines.append("")
        lines.extend(self._build_conclusive_verdict(context, sl, tp, atr, is_fx))

        return "\n".join(lines)

    def _build_conclusive_verdict(
        self,
        context: MarketContext,
        sl: float | None,
        tp: float | None,
        atr: float,
        is_fx: bool,
    ) -> list[str]:
        """Construct a structured, fully coherent trading verdict block (resumen conclusivo y parámetros de riesgo)."""
        price = context.current_price
        quant = context.quant_score
        regime = context.market_regime
        action = (context.signal.action or "").upper()
        direction = (context.signal.direction or "").upper()
        confidence = context.signal.confidence
        conf_pct = confidence * 100.0 if confidence <= 1.0 else confidence
        rsi = context.technical_indicators.get("rsi")
        warnings = list(context.signal.warnings)

        def _fmt(val: float | None) -> str:
            if val is None:
                return "N/A"
            if is_fx or val < 10:
                return f"${val:,.4f}"
            return f"${val:,.2f}"

        rsi_str = f" y un RSI en ~{rsi:.1f}" if rsi is not None else ""
        warn_str = f" ({', '.join(warnings)})" if warnings else ""

        # Strict coherence: If action is WAIT or confidence is low, NEVER say "Sí, favorece compras"
        if "WAIT" in action or "HOLD" in action:
            if "LONG" in direction:
                v_title = "En Espera / Precaución (NO entrar ahora):"
                v_desc = (
                    f"{v_title} Aunque la estructura de fondo muestra sesgo alcista (`{regime}`), "
                    f"el motor cuantitativo mantiene la señal en espera (`WAIT`) con confianza del {conf_pct:.1f}%. "
                    f"Existen advertencias activas{warn_str}, por lo que ingresar a comprar en este instante conlleva un riesgo elevado de falso impulso o retroceso. "
                    f"Se aconseja esperar un retroceso a soporte o confirmación de volumen institucional."
                )
            elif "SHORT" in direction:
                v_title = "En Espera / Precaución (NO entrar ahora):"
                v_desc = (
                    f"{v_title} Aunque el sesgo técnico muestra presión bajista (`{regime}`), "
                    f"el motor mantiene la señal en espera (`WAIT`) con confianza del {conf_pct:.1f}%. "
                    f"Existen advertencias activas{warn_str}. Se aconseja no entrar hasta confirmar volumen o ruptura."
                )
            else:
                v_title = "En Espera / Neutral (NO entrar ahora):"
                v_desc = (
                    f"{v_title} El mercado se encuentra en consolidación o indecisión bajo régimen `{regime}` "
                    f"con el precio en {_fmt(price)}{rsi_str}. "
                    f"La puntuación cuantitativa ({quant:.1f}/100) indica que no hay ventaja estadística suficiente; conviene aguardar confirmación."
                )
        elif "BUY" in action or "LONG" in action:
            if quant >= 70.0 and conf_pct >= 60.0 and not any("Momentum débil" in w for w in warnings):
                v_title = "Sí, el sesgo matemático favorece las compras (LONG)."
                v_desc = (
                    f"{v_title} El par se encuentra en una estructura alcista confirmada bajo régimen `{regime}` "
                    f"con el precio cotizando en {_fmt(price)}{rsi_str}. "
                    f"La puntuación cuantitativa ({quant:.1f}/100) y la confianza ({conf_pct:.1f}%) respaldan la entrada."
                )
            else:
                v_title = "Posible compra con cautela (LONG moderado):"
                v_desc = (
                    f"{v_title} La señal marca compra pero con confianza moderada ({conf_pct:.1f}%){warn_str}. "
                    f"Se recomienda tamaño de posición reducido y estricto respeto al Stop Loss."
                )
        elif "SELL" in action or "SHORT" in action:
            if quant >= 70.0 and conf_pct >= 60.0:
                v_title = "Sí, el sesgo matemático favorece las ventas (SHORT)."
                v_desc = (
                    f"{v_title} El par se encuentra bajo presión bajista confirmada en régimen `{regime}` "
                    f"con el precio en {_fmt(price)}{rsi_str}. "
                    f"La fuerza técnica y el flujo vendedor respaldan la posición corta o mantenerse fuera de compras."
                )
            else:
                v_title = "Precaución: Presión vendedora detectada (SHORT moderado):"
                v_desc = (
                    f"{v_title} El activo enfrenta debilidad técnica en régimen `{regime}` "
                    f"con el precio en {_fmt(price)}{rsi_str}{warn_str}. "
                    f"El modelo cuantitativo no recomienda compras en este entorno."
                )
        else:
            v_title = "En Espera / Neutral: No se recomienda entrar en este momento."
            v_desc = (
                f"{v_title} El mercado se encuentra en rango bajo régimen `{regime}` con precio en {_fmt(price)}. "
                f"Conviene aguardar una ruptura con volumen institucional."
            )

        # 2. Concrete risk parameters
        spread = min(0.25 * atr, price * 0.001) if price > 0 else 0.0
        if "SELL" in action or "SHORT" in direction:
            e_min = price
            e_max = price + spread
        else:
            e_min = max(0.0, price - spread)
            e_max = price

        entry_text = f"Zona de {_fmt(e_min)} – {_fmt(e_max)}"

        if sl is not None and price > 0:
            sl_pct = abs(price - sl) / price * 100
            sl_text = f"{_fmt(sl)} (Riesgo controlado de ~{sl_pct:.2f}%)"
        else:
            sl_text = "Nivel de soporte dinámico por volatilidad ATR"

        if tp is not None and price > 0:
            tp_pct = abs(tp - price) / price * 100
            if sl is not None and abs(price - sl) > 0:
                rr = abs(tp - price) / abs(price - sl)
                rr_text = f", Ratio Riesgo:Beneficio de 1 : {rr:.1f}" if rr >= 0.1 else ""
            else:
                rr_text = ""
            tp_text = f"{_fmt(tp)} (Objetivo técnico ~+{tp_pct:.2f}%{rr_text})"
        else:
            tp_text = "Nivel de resistencia dinámica por volatilidad ATR"

        return [
            "---",
            "### 🏁 Conclusión Operativa y Veredicto Técnico:",
            f"* **Respuesta técnica**: {v_desc}",
            "* **Parámetros de Riesgo Sugeridos**:",
            f"  * **Entrada**: {entry_text}",
            f"  * **Stop Loss (Corte de pérdida)**: {sl_text}",
            f"  * **Take Profit (Toma de beneficio)**: {tp_text}",
        ]