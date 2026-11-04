import math

try:
    from .constants import (
        DECISION_FAVORABLE,
        DECISION_WAIT_CONFIRMATION,
        DECISION_WEAK_CONTEXT,
        RISK_HIGH,
        RISK_LOW,
        RISK_MEDIUM,
        VOLUME_ABOVE_AVERAGE,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        DECISION_FAVORABLE,
        DECISION_WAIT_CONFIRMATION,
        DECISION_WEAK_CONTEXT,
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

            risks.append("RSI elevado, movimiento extendido.")

        elif analysis["rsi"] <= 25:
            risk_score += 1

            risks.append("RSI bajo, posible agotamiento.")

        # ==========================
        # Volumen
        # ==========================

        if analysis["volume"] != VOLUME_ABOVE_AVERAGE:
            risk_score += 1

            risks.append("Volumen sin confirmación.")

        # ==========================
        # Distancia del precio al POC
        # ==========================

        distance = abs(analysis["price"] - profile["poc"])

        atr = analysis["atr"]

        if distance > atr * 2:
            risk_score += 1

            risks.append("Precio alejado del POC.")

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
            "final_confidence": max(0, 100 - adjustment),
            "risks": risks,
        }

    @staticmethod
    def _positive_finite(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    def calculate_levels(self, entry_price, stop_loss, take_profit, direction):
        """Validate effective levels and calculate gross reward/risk without costs."""
        result = {
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_distance": None,
            "reward_distance": None,
            "gross_risk_reward": None,
            "reason": None,
        }
        direction = str(direction).strip().upper()
        if direction not in {"LONG", "SHORT"}:
            result["reason"] = "Dirección no operable: se requiere LONG o SHORT."
            return result

        values = (entry_price, stop_loss, take_profit)
        if any(value is None for value in values):
            result["reason"] = "Faltan entrada, Stop Loss o Take Profit."
            return result
        entry, stop, target = (self._positive_finite(value) for value in values)
        if any(value is None for value in (entry, stop, target)):
            result["reason"] = (
                "Entrada, Stop Loss y Take Profit deben ser finitos y positivos."
            )
            return result

        if direction == "LONG":
            if stop >= entry:
                result["reason"] = (
                    "El Stop Loss LONG debe estar por debajo de la entrada."
                )
                return result
            if target <= entry:
                result["reason"] = (
                    "El Take Profit LONG debe estar por encima de la entrada."
                )
                return result
            risk_distance, reward_distance = entry - stop, target - entry
        else:
            if stop <= entry:
                result["reason"] = (
                    "El Stop Loss SHORT debe estar por encima de la entrada."
                )
                return result
            if target >= entry:
                result["reason"] = (
                    "El Take Profit SHORT debe estar por debajo de la entrada."
                )
                return result
            risk_distance, reward_distance = stop - entry, entry - target

        ratio = reward_distance / risk_distance
        if not math.isfinite(ratio):
            result["reason"] = "La relación beneficio/riesgo no es finita."
            return result
        result.update(
            {
                "entry_price": entry,
                "stop_loss": stop,
                "take_profit": target,
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
                "gross_risk_reward": ratio,
            }
        )
        return result

    def plan_from_decision(
        self,
        *,
        decision,
        direction,
        reference_price,
        atr,
        sl_multiplier,
        tp_multiplier,
    ):
        """Build an indicative ATR plan; no execution trigger or fill is inferred."""
        reference = self._positive_finite(reference_price)
        plan = {
            "status": "NO DISPONIBLE",
            "direction": "SIN OPERACIÓN",
            "reference_price": reference,
            "atr": None,
            "entry_confirmed": False,
            "methodology": None,
            **self.calculate_levels(None, None, None, direction),
        }

        if decision == DECISION_WAIT_CONFIRMATION:
            plan.update(
                status="ESPERANDO CONFIRMACIÓN",
                reason="La decisión requiere confirmación.",
            )
            return plan
        if decision == DECISION_WEAK_CONTEXT:
            plan.update(
                status="DESCARTADA", reason="El contexto no justifica una entrada."
            )
            return plan
        if decision != DECISION_FAVORABLE:
            plan["reason"] = (
                "No se reconoce una decisión favorable para planificar niveles."
            )
            return plan

        normalized_direction = str(direction).strip().upper()
        if normalized_direction not in {"LONG", "SHORT"}:
            plan["reason"] = "Dirección no operable: se requiere LONG o SHORT."
            return plan
        atr_value = self._positive_finite(atr)
        plan["atr"] = atr_value
        sl_factor = self._positive_finite(sl_multiplier)
        tp_factor = self._positive_finite(tp_multiplier)
        if (
            reference is None
            or atr_value is None
            or sl_factor is None
            or tp_factor is None
        ):
            plan["reason"] = (
                "Faltan precio, ATR o multiplicadores válidos para calcular niveles."
            )
            return plan

        if normalized_direction == "LONG":
            stop = reference - atr_value * sl_factor
            target = reference + atr_value * tp_factor
        else:
            stop = reference + atr_value * sl_factor
            target = reference - atr_value * tp_factor

        levels = self.calculate_levels(reference, stop, target, normalized_direction)
        if levels["reason"] is not None:
            plan["reason"] = levels["reason"]
            return plan
        plan.update(levels)
        plan.update(
            {
                "status": "CANDIDATA",
                "direction": normalized_direction,
                "methodology": "ATR de la vela analizada con multiplicadores de decisión",
                "reason": "Entrada propuesta al precio de referencia; falta confirmación de ejecución.",
            }
        )
        return plan
