import pandas as pd

try:
    from .constants import (
        MOMENTUM_BEARISH_PRESSURE,
        MOMENTUM_EXTENDED,
        MOMENTUM_POSITIVE,
        MOMENTUM_WEAK,
        PROFILE_ABOVE_VALUE_AREA,
        PROFILE_BELOW_VALUE_AREA,
        PROFILE_INSIDE_VALUE_AREA,
        PROFILE_NO_DATA,
        TREND_BEARISH,
        TREND_BULLISH,
        TREND_SIDEWAYS,
        VOLATILITY_HIGH,
        VOLATILITY_LOW,
        VOLATILITY_MODERATE,
        VOLUME_ABOVE_AVERAGE,
        VOLUME_BELOW_AVERAGE,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        MOMENTUM_BEARISH_PRESSURE,
        MOMENTUM_EXTENDED,
        MOMENTUM_POSITIVE,
        MOMENTUM_WEAK,
        PROFILE_ABOVE_VALUE_AREA,
        PROFILE_BELOW_VALUE_AREA,
        PROFILE_INSIDE_VALUE_AREA,
        PROFILE_NO_DATA,
        TREND_BEARISH,
        TREND_BULLISH,
        TREND_SIDEWAYS,
        VOLATILITY_HIGH,
        VOLATILITY_LOW,
        VOLATILITY_MODERATE,
        VOLUME_ABOVE_AVERAGE,
        VOLUME_BELOW_AVERAGE,
    )


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
            trend = TREND_BULLISH

        elif price < ema50 < ema200:
            trend = TREND_BEARISH

        else:
            trend = TREND_SIDEWAYS


        analysis["trend"] = trend


        # =========================
        # Momentum RSI
        # =========================

        if rsi >= 70:
            momentum = MOMENTUM_EXTENDED

        elif rsi >= 50:
            momentum = MOMENTUM_POSITIVE

        elif rsi >= 30:
            momentum = MOMENTUM_WEAK

        else:
            momentum = MOMENTUM_BEARISH_PRESSURE


        analysis["momentum"] = momentum


        # =========================
        # Volatilidad
        # =========================

        atr_percent = (
            atr / price
        ) * 100


        if atr_percent > 2:
            volatility = VOLATILITY_HIGH

        elif atr_percent > 1:
            volatility = VOLATILITY_MODERATE

        else:
            volatility = VOLATILITY_LOW


        analysis["volatility"] = volatility


        # =========================
        # Volumen
        # =========================

        if volume > avg_volume:
            volume_state = VOLUME_ABOVE_AVERAGE

        else:
            volume_state = VOLUME_BELOW_AVERAGE


        analysis["volume"] = volume_state


        # =========================
        # Volume Profile
        # =========================

        profile_state = PROFILE_NO_DATA


        if volume_profile:

            poc = volume_profile["poc"]
            vah = volume_profile["vah"]
            val = volume_profile["val"]


            if price > vah:
                profile_state = (
                    PROFILE_ABOVE_VALUE_AREA
                )

            elif price < val:
                profile_state = (
                    PROFILE_BELOW_VALUE_AREA
                )

            else:
                profile_state = (
                    PROFILE_INSIDE_VALUE_AREA
                )


            analysis["poc"] = poc
            analysis["vah"] = vah
            analysis["val"] = val


        analysis["profile"] = profile_state


        # =========================
        # Score
        # =========================

        score = 0


        if trend == TREND_BULLISH:
            score += 2

        elif trend == TREND_BEARISH:
            score -= 2


        if rsi >= 50:
            score += 1

        elif rsi < 30:
            score -= 1


        if volume > avg_volume:
            score += 1


        if profile_state == PROFILE_INSIDE_VALUE_AREA:
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

