import pandas as pd


class MarketEngine:

    def analyze(self, df: pd.DataFrame):

        latest = df.iloc[-1]

        analysis = {}

        # -------------------------
        # Momentum (RSI)
        # -------------------------

        rsi = latest["rsi"]

        if rsi >= 70:
            momentum = "Fuerte pero sobreextendido"
        elif rsi >= 50:
            momentum = "Positivo"
        elif rsi >= 30:
            momentum = "Débil"
        else:
            momentum = "Presión bajista"

        analysis["momentum"] = momentum


        # -------------------------
        # Volatilidad (ATR)
        # -------------------------

        atr = latest["atr"]
        price = latest["close"]

        atr_percentage = (atr / price) * 100

        if atr_percentage > 2:
            volatility = "Alta"
        elif atr_percentage > 1:
            volatility = "Moderada"
        else:
            volatility = "Baja"

        analysis["volatility"] = volatility


        # -------------------------
        # Volumen
        # -------------------------

        volume = latest["volume"]
        avg_volume = latest["volume_average"]

        if volume > avg_volume:
            volume_state = "Superior al promedio"
        else:
            volume_state = "Inferior al promedio"

        analysis["volume"] = volume_state


        # -------------------------
        # Evaluación general
        # -------------------------

        score = 0

        if rsi >= 50:
            score += 1

        if volume > avg_volume:
            score += 1

        if volatility != "Alta":
            score += 1


        if score >= 2:
            context = "Contexto favorable, buscar confirmación"
        elif score == 1:
            context = "Contexto mixto, esperar"
        else:
            context = "Contexto débil"

        analysis["market_context"] = context


        analysis["price"] = price
        analysis["rsi"] = round(rsi, 2)
        analysis["atr"] = round(atr, 2)

        return analysis