try:
    from .constants import (
        MOMENTUM_POSITIVE,
        SIGNAL_BULLISH,
        SIGNAL_MODERATE,
        SIGNAL_WEAK,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_ABOVE_AVERAGE,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        MOMENTUM_POSITIVE,
        SIGNAL_BULLISH,
        SIGNAL_MODERATE,
        SIGNAL_WEAK,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_ABOVE_AVERAGE,
    )


class SignalEngine:


    def evaluate(self, analysis, profile):


        score = 0

        positives = []

        risks = []


        # Tendencia

        if analysis["trend"] == TREND_BULLISH:

            score += 1

            positives.append(
                "Tendencia alcista confirmada"
            )


        elif analysis["trend"] == TREND_BEARISH:

            score -= 1

            risks.append(
                "Tendencia bajista activa"
            )


        # Momentum

        if analysis["momentum"] == MOMENTUM_POSITIVE:

            score += 1

            positives.append(
                "Momentum positivo"
            )


        else:

            risks.append(
                "Momentum débil"
            )


        # Ubicación respecto al valor

        if analysis["price"] > profile["vah"]:

            score += 1

            positives.append(
                "Precio sobre VAH"
            )


        elif analysis["price"] < profile["val"]:

            score -= 1

            risks.append(
                "Precio debajo de VAL"
            )


        # Volumen

        if analysis["volume"] == VOLUME_ABOVE_AVERAGE:

            score += 1

            positives.append(
                "Volumen confirma movimiento"
            )


        else:

            risks.append(
                "Volumen sin confirmación"
            )


        # Resultado

        if score >= 3:

            state = SIGNAL_BULLISH

        elif score >= 1:

            state = SIGNAL_MODERATE

        else:

            state = SIGNAL_WEAK



        confidence = max(
            0,
            min(score * 20 + 40, 95)
        )


        return {


            "state": state,


            "confidence": confidence,


            "positives": positives,


            "risks": risks,


            "score": score

        }
