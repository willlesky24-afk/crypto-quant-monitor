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

        if analysis["trend"] == "Alcista":

            breakdown["trend"] = 25

        elif analysis["trend"] == "Bajista":

            breakdown["trend"] = -25

        else:

            breakdown["trend"] = 0



        # ==========================
        # Momentum
        # ==========================

        if analysis["momentum"] == "Positivo":

            breakdown["momentum"] = 20

        elif analysis["momentum"] == "Negativo":

            breakdown["momentum"] = -20

        else:

            breakdown["momentum"] = 5



        # ==========================
        # Volumen
        # ==========================

        if analysis["volume"] == "Superior al promedio":

            breakdown["volume"] = 15

        else:

            breakdown["volume"] = 5



        # ==========================
        # Zona de valor
        # ==========================

        if "Por encima" in analysis["profile"]:

            breakdown["profile"] = 15

        elif "Debajo" in analysis["profile"]:

            breakdown["profile"] = -15

        else:

            breakdown["profile"] = 10



        # ==========================
        # Riesgo
        # ==========================

        if risk["level"] == "Bajo":

            breakdown["risk"] = 0

        elif risk["level"] == "Medio":

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