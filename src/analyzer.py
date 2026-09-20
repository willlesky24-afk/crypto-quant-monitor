try:
    from .constants import (
        MOMENTUM_EXTENDED,
        MOMENTUM_POSITIVE,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_BELOW_AVERAGE,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        MOMENTUM_EXTENDED,
        MOMENTUM_POSITIVE,
        TREND_BEARISH,
        TREND_BULLISH,
        VOLUME_BELOW_AVERAGE,
    )


class MarketAnalyzer:


    def generate_summary(
        self,
        analysis: dict
    ):

        trend = analysis["trend"]
        momentum = analysis["momentum"]
        volume = analysis["volume"]
        profile = analysis["profile"]
        score = analysis["score"]


        summary = []


        # Tendencia

        if trend == TREND_BULLISH:

            summary.append(
                "El mercado mantiene una estructura alcista."
            )

        elif trend == TREND_BEARISH:

            summary.append(
                "El mercado presenta una estructura bajista."
            )

        else:

            summary.append(
                "El mercado se encuentra sin una tendencia clara."
            )


        # Momentum

        if momentum == MOMENTUM_EXTENDED:

            summary.append(
                "El impulso es positivo, pero el movimiento "
                "muestra señales de extensión."
            )

        elif momentum == MOMENTUM_POSITIVE:

            summary.append(
                "El momentum acompaña el movimiento actual."
            )


        # Volumen

        if volume == VOLUME_BELOW_AVERAGE:

            summary.append(
                "El volumen actual está por debajo del promedio, "
                "por lo que se requiere confirmación."
            )

        else:

            summary.append(
                "El volumen acompaña el movimiento."
            )


        # Zona de valor

        summary.append(
            f"Ubicación respecto al volumen: {profile}."
        )


        # Conclusión

        if score >= 4:

            conclusion = (
                "Contexto interesante, pero se recomienda "
                "esperar confirmación antes de actuar."
            )

        elif score >= 2:

            conclusion = (
                "Existen factores positivos, aunque "
                "faltan confirmaciones adicionales."
            )

        else:

            conclusion = (
                "El contexto actual no presenta suficiente "
                "confluencia."
            )


        return {
            "summary": " ".join(summary),
            "conclusion": conclusion
        }
