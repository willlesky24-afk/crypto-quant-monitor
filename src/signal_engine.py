class SignalEngine:


    def evaluate(self, analysis, profile):


        score = 0

        positives = []

        risks = []


        # Tendencia

        if analysis["trend"] == "Alcista":

            score += 1

            positives.append(
                "Tendencia alcista confirmada"
            )


        elif analysis["trend"] == "Bajista":

            score -= 1

            risks.append(
                "Tendencia bajista activa"
            )


        # Momentum

        if analysis["momentum"] == "Positivo":

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

        if analysis["volume"] == "Superior al promedio":

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

            state = "🟢 Señal alcista"

        elif score >= 1:

            state = "🟡 Señal moderada"

        else:

            state = "🔴 Señal débil"



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