try:
    from .constants import (
        RISK_HIGH,
        RISK_LOW,
        RISK_MEDIUM,
        VOLUME_ABOVE_AVERAGE,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        RISK_HIGH,
        RISK_LOW,
        RISK_MEDIUM,
        VOLUME_ABOVE_AVERAGE,
    )


class RiskEngine:


    def evaluate(self, analysis, profile):


        risks = []

        risk_score = 0


        # ==========================
        # RSI
        # ==========================

        if analysis["rsi"] >= 75:

            risk_score += 1

            risks.append(
                "RSI elevado, movimiento extendido."
            )


        elif analysis["rsi"] <= 25:

            risk_score += 1

            risks.append(
                "RSI bajo, posible agotamiento."
            )


        # ==========================
        # Volumen
        # ==========================

        if analysis["volume"] != VOLUME_ABOVE_AVERAGE:

            risk_score += 1

            risks.append(
                "Volumen sin confirmación."
            )


        # ==========================
        # Distancia del precio al POC
        # ==========================

        distance = abs(
            analysis["price"] - profile["poc"]
        )


        atr = analysis["atr"]


        if distance > atr * 2:

            risk_score += 1

            risks.append(
                "Precio alejado del POC."
            )


        # ==========================
        # Nivel de riesgo
        # ==========================

        if risk_score >= 3:

            level = RISK_HIGH

        elif risk_score >= 1:

            level = RISK_MEDIUM

        else:

            level = RISK_LOW



        # ==========================
        # Ajuste de confianza
        # ==========================

        adjustment = risk_score * 10


        return {


            "level": level,


            "risk_score": risk_score,


            "adjustment": adjustment,


            "final_confidence": max(
                0,
                100 - adjustment
            ),


            "risks": risks

        }
