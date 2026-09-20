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

        high = values[:, 0]
        low = values[:, 1]
        close = values[:, 2]
        volume = values[:, 3]

        prices = (high + low + close) / 3.0

        p_min = float(prices.min())
        p_max = float(prices.max())

        if p_min == p_max:
            price = round(float(prices[0]), 2)

            return {
                "poc": price,
                "vah": price,
                "val": price
            }

        price_range = np.linspace(
            p_min,
            p_max,
            bins
        )

        volume_profile, _ = np.histogram(
            prices,
            bins=price_range,
            weights=volume
        )

        max_index = int(np.argmax(
            volume_profile
        ))

        poc = (
            price_range[max_index] +
            price_range[max_index + 1]
        ) / 2.0

        total_volume = float(volume_profile.sum())

        target_volume = total_volume * 0.70

        accumulated = 0.0

        low_index = max_index
        high_index = max_index

        while accumulated < target_volume:

            if low_index > 0:
                low_index -= 1

            if high_index < len(volume_profile) - 1:
                high_index += 1

            accumulated = float(volume_profile[
                low_index:high_index + 1
            ].sum())

        val = price_range[low_index]

        vah = price_range[
            high_index + 1
        ]

        return {
            "poc": round(float(poc), 2),
            "vah": round(float(vah), 2),
            "val": round(float(val), 2)
        }
