try:
    from .constants import (
        DECISION_FAVORABLE,
        DECISION_WAIT_CONFIRMATION,
        DECISION_WEAK_CONTEXT,
        RISK_LOW,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        DECISION_FAVORABLE,
        DECISION_WAIT_CONFIRMATION,
        DECISION_WEAK_CONTEXT,
        RISK_LOW,
    )


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


        if confidence >= 80 and risk["level"] == RISK_LOW:

            decision = DECISION_FAVORABLE


        elif confidence >= 60:

            decision = DECISION_WAIT_CONFIRMATION


        else:

            decision = DECISION_WEAK_CONTEXT



        return {


            "decision": decision,


            "confidence": confidence,


            "positives": positives,


            "warnings": warnings,


            "market_state": intelligence["state"]

        }
