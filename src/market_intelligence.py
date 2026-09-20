try:
    from .constants import (
        INTELLIGENCE_HIGH_CONFLUENCE,
        INTELLIGENCE_INTERESTING,
        INTELLIGENCE_WEAK,
        RISK_LOW,
        RISK_MEDIUM,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_BELOW_AVERAGE,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        INTELLIGENCE_HIGH_CONFLUENCE,
        INTELLIGENCE_INTERESTING,
        INTELLIGENCE_WEAK,
        RISK_LOW,
        RISK_MEDIUM,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_BELOW_AVERAGE,
    )


class MarketIntelligence:


    def evaluate(self, analysis: dict):

        score = analysis["score"]

        trend = analysis["trend"]
        volume = analysis["volume"]
        momentum = analysis["momentum"]
        profile = analysis["profile"]


        if score >= 4:
            state = INTELLIGENCE_HIGH_CONFLUENCE

        elif score >= 2:
            state = INTELLIGENCE_INTERESTING

        else:
            state = INTELLIGENCE_WEAK


        if volume == VOLUME_BELOW_AVERAGE:

            risk = RISK_MEDIUM

            risk_reason = (
                "El movimiento no está acompañado "
                "por expansión de volumen."
            )

        else:

            risk = RISK_LOW

            risk_reason = (
                "El volumen acompaña la estructura actual."
            )


        if trend == TREND_BULLISH:

            trend_text = (
                "La estructura favorece compradores "
                "mientras el precio mantiene tendencia positiva."
            )

        elif trend == TREND_BEARISH:

            trend_text = (
                "La estructura muestra presión vendedora."
            )

        else:

            trend_text = (
                "No existe una tendencia dominante clara."
            )


        report = {

            "state": state,

            "risk": risk,

            "risk_reason": risk_reason,

            "trend_analysis": trend_text,

            "momentum": momentum,

            "volume": volume,

            "profile": profile

        }


        return report
