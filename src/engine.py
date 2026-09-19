import pandas as pd


class MarketEngine:

    def analyze(
        self,
        df: pd.DataFrame,
        volume_profile: dict = None
    ):

        latest = df.iloc[-1]

        price = float(latest["close"])
        rsi = float(latest["rsi"])
        atr = float(latest["atr"])
        volume = float(latest["volume"])
        avg_volume = float(latest["volume_average"])

        ema50 = float(latest["ema_50"])
        ema200 = float(latest["ema_200"])


        analysis = {}


        # =========================
        # Tendencia
        # =========================

        if price > ema50 > ema200:
            trend = "Alcista"

        elif price < ema50 < ema200:
            trend = "Bajista"

        else:
            trend = "Lateral"


        analysis["trend"] = trend


        # =========================
        # Momentum RSI
        # =========================

        if rsi >= 70:
            momentum = "Fuerte pero extendido"

        elif rsi >= 50:
            momentum = "Positivo"

        elif rsi >= 30:
            momentum = "Débil"

        else:
            momentum = "Presión bajista"


        analysis["momentum"] = momentum


        # =========================
        # Volatilidad
        # =========================

        atr_percent = (
            atr / price
        ) * 100


        if atr_percent > 2:
            volatility = "Alta"

        elif atr_percent > 1:
            volatility = "Moderada"

        else:
            volatility = "Baja"


        analysis["volatility"] = volatility


        # =========================
        # Volumen
        # =========================

        if volume > avg_volume:
            volume_state = "Superior al promedio"

        else:
            volume_state = "Inferior al promedio"


        analysis["volume"] = volume_state


        # =========================
        # Volume Profile
        # =========================

        profile_state = "Sin datos"


        if volume_profile:

            poc = volume_profile["poc"]
            vah = volume_profile["vah"]
            val = volume_profile["val"]


            if price > vah:
                profile_state = (
                    "Por encima del área de valor"
                )

            elif price < val:
                profile_state = (
                    "Por debajo del área de valor"
                )

            else:
                profile_state = (
                    "Dentro del área de valor"
                )


            analysis["poc"] = poc
            analysis["vah"] = vah
            analysis["val"] = val


        analysis["profile"] = profile_state


        # =========================
        # Score
        # =========================

        score = 0


        if trend == "Alcista":
            score += 2

        elif trend == "Bajista":
            score -= 2


        if rsi >= 50:
            score += 1

        elif rsi < 30:
            score -= 1


        if volume > avg_volume:
            score += 1


        if profile_state == "Dentro del área de valor":
            score += 1


        analysis["score"] = score


        # =========================
        # Interpretación
        # =========================

        if score >= 4:

            context = (
                "Alta confluencia, "
                "requiere confirmación"
            )

        elif score >= 2:

            context = (
                "Contexto interesante, "
                "esperar confirmación"
            )

        elif score >= 0:

            context = (
                "Contexto neutral"
            )

        else:

            context = (
                "Contexto débil"
            )


        analysis["market_context"] = context


        analysis["price"] = round(price, 2)
        analysis["rsi"] = round(rsi, 2)
        analysis["atr"] = round(atr, 2)


        return analysis

