class DecisionEngine:


    def evaluate(
        self,
        signal,
        risk,
        intelligence
    ):


        confidence = signal["confidence"]


        # Ajuste por riesgo

        confidence -= risk["adjustment"]


        confidence = max(
            0,
            min(confidence, 100)
        )


        positives = signal["positives"]


        warnings = []


        warnings.extend(
            signal["risks"]
        )


        warnings.extend(
            risk["risks"]
        )



        # Decisión final


        if confidence >= 80 and risk["level"] == "Bajo":

            decision = "🟢 Condición favorable"


        elif confidence >= 60:

            decision = "🟡 Esperar confirmación"


        else:

            decision = "🔴 Contexto débil"



        return {


            "decision": decision,


            "confidence": confidence,


            "positives": positives,


            "warnings": warnings,


            "market_state": intelligence["state"]

        }