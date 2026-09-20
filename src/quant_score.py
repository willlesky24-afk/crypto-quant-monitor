try:
    from .constants import (
        MOMENTUM_BEARISH_PRESSURE,
        MOMENTUM_POSITIVE,
        PROFILE_ABOVE_VALUE_AREA,
        PROFILE_BELOW_VALUE_AREA,
        RISK_LOW,
        RISK_MEDIUM,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_ABOVE_AVERAGE,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        MOMENTUM_BEARISH_PRESSURE,
        MOMENTUM_POSITIVE,
        PROFILE_ABOVE_VALUE_AREA,
        PROFILE_BELOW_VALUE_AREA,
        RISK_LOW,
        RISK_MEDIUM,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_ABOVE_AVERAGE,
    )


class QuantScore:


    def calculate(
        self,
        analysis,
        signal,
        risk
    ):

        score = 40

        breakdown = {}


        # ==========================
        # Tendencia
        # ==========================

        if analysis["trend"] == TREND_BULLISH:

            breakdown["trend"] = 25

        elif analysis["trend"] == TREND_BEARISH:

            breakdown["trend"] = -25

        else:

            breakdown["trend"] = 0



        # ==========================
        # Momentum
        # ==========================

        if analysis["momentum"] == MOMENTUM_POSITIVE:

            breakdown["momentum"] = 20

        elif analysis["momentum"] == MOMENTUM_BEARISH_PRESSURE:

            breakdown["momentum"] = -20

        else:

            breakdown["momentum"] = 5



        # ==========================
        # Volumen
        # ==========================

        if analysis["volume"] == VOLUME_ABOVE_AVERAGE:

            breakdown["volume"] = 15

        else:

            breakdown["volume"] = 5



        # ==========================
        # Zona de valor
        # ==========================

        if analysis["profile"] == PROFILE_ABOVE_VALUE_AREA:

            breakdown["profile"] = 15

        elif analysis["profile"] == PROFILE_BELOW_VALUE_AREA:

            breakdown["profile"] = -15

        else:

            breakdown["profile"] = 10



        # ==========================
        # Riesgo
        # ==========================

        if risk["level"] == RISK_LOW:

            breakdown["risk"] = 0

        elif risk["level"] == RISK_MEDIUM:

            breakdown["risk"] = -10

        else:

            breakdown["risk"] = -25



        # ==========================
        # Score final
        # ==========================

        score = score + sum(
            breakdown.values()
        )


        score = max(
            0,
            min(score, 100)
        )


        # ==========================
        # Etiqueta
        # ==========================

        if score >= 80:

            label = "Contexto fuerte"

        elif score >= 60:

            label = "Contexto favorable"

        elif score >= 40:

            label = "Contexto neutral"

        else:

            label = "Contexto débil"



        return {

            "score": score,

            "label": label,

            "breakdown": breakdown

        }
