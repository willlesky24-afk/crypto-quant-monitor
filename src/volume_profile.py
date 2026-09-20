import numpy as np
import pandas as pd


class VolumeProfile:


    def calculate(
        self,
        df: pd.DataFrame,
        bins: int = 24
    ):
        """
        Calcula POC, VAH y VAL
        usando distribución de volumen por precio.
        """

        required_columns = {"high", "low", "close", "volume"}
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Faltan columnas requeridas: {missing}")

        if df.empty:
            raise ValueError("No se puede calcular el perfil con datos vacíos")

        if isinstance(bins, bool) or not isinstance(bins, (int, np.integer)):
            raise ValueError("bins debe ser un entero mayor o igual a 2")

        if bins < 2:
            raise ValueError("bins debe ser un entero mayor o igual a 2")

        values = df[["high", "low", "close", "volume"]].to_numpy(
            dtype=float
        )

        if not np.isfinite(values).all():
            raise ValueError("Los precios y el volumen deben ser valores finitos")

        prices = (
            df["high"] +
            df["low"] +
            df["close"]
        ) / 3


        volume = df["volume"]


        if prices.min() == prices.max():
            price = round(float(prices.iloc[0]), 2)

            return {
                "poc": price,
                "vah": price,
                "val": price
            }


        price_range = np.linspace(
            prices.min(),
            prices.max(),
            bins
        )


        volume_profile = []


        last_interval = len(price_range) - 2


        for i in range(len(price_range)-1):

            if i == last_interval:
                mask = (
                    (prices >= price_range[i]) &
                    (prices <= price_range[i+1])
                )

            else:
                mask = (
                    (prices >= price_range[i]) &
                    (prices < price_range[i+1])
                )

            volume_profile.append(
                volume[mask].sum()
            )


        volume_profile = np.array(
            volume_profile
        )


        max_index = np.argmax(
            volume_profile
        )


        poc = (
            price_range[max_index] +
            price_range[max_index + 1]
        ) / 2


        total_volume = volume_profile.sum()


        target_volume = total_volume * 0.70


        accumulated = 0

        low_index = max_index
        high_index = max_index


        while accumulated < target_volume:

            if low_index > 0:
                low_index -= 1

            if high_index < len(volume_profile)-1:
                high_index += 1


            accumulated = volume_profile[
                low_index:high_index+1
            ].sum()


        val = price_range[low_index]

        vah = price_range[
            high_index + 1
        ]


        return {
            "poc": round(float(poc), 2),
            "vah": round(float(vah), 2),
            "val": round(float(val), 2)
        }
