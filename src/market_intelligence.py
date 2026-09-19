class MarketIntelligence:


    def evaluate(self, analysis: dict):

        score = analysis["score"]

        trend = analysis["trend"]
        volume = analysis["volume"]
        momentum = analysis["momentum"]
        profile = analysis["profile"]


        if score >= 4:
            state = "🟢 Alta confluencia"

        elif score >= 2:
            state = "🟡 Contexto interesante"

        else:
            state = "🔴 Contexto débil"


        if volume == "Inferior al promedio":

            risk = "Medio"

            risk_reason = (
                "El movimiento no está acompañado "
                "por expansión de volumen."
            )

        else:

            risk = "Bajo"

            risk_reason = (
                "El volumen acompaña la estructura actual."
            )


        if trend == "Alcista":

            trend_text = (
                "La estructura favorece compradores "
                "mientras el precio mantiene tendencia positiva."
            )

        elif trend == "Bajista":

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