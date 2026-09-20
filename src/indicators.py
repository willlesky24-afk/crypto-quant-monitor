import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


class TechnicalIndicators:

    def add_rsi(
        self,
        df: pd.DataFrame,
        period: int = 14
    ):
        """
        Calcula RSI.
        """

        indicator = RSIIndicator(
            close=df["close"],
            window=period
        )

        df["rsi"] = indicator.rsi()

        return df


    def add_atr(
        self,
        df: pd.DataFrame,
        period: int = 14
    ):
        """
        Calcula ATR (volatilidad).
        """

        indicator = AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=period
        )

        df["atr"] = indicator.average_true_range()

        return df


    def add_volume_average(
        self,
        df: pd.DataFrame,
        period: int = 20
    ):
        """
        Media de volumen.
        """

        df["volume_average"] = (
            df["volume"]
            .rolling(period)
            .mean()
        )

        return df


    def calculate_all(
        self,
        df: pd.DataFrame
    ):

        df = self.add_rsi(df)
        df = self.add_atr(df)
        df = self.add_volume_average(df)
        df = self.add_ema(df)

        return df


    def add_ema(
        self,
        df: pd.DataFrame,
        fast_period: int = 50,
        slow_period: int = 200
    ):
        """
        Calcula medias exponenciales para identificar tendencia.
        """

        df["ema_50"] = (
            df["close"]
            .ewm(span=fast_period, adjust=False)
            .mean()
        )

        df["ema_200"] = (
            df["close"]
            .ewm(span=slow_period, adjust=False)
            .mean()
        )

        return df