import pandas as pd
import numpy as np


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

        prices = (
            df["high"] +
            df["low"] +
            df["close"]
        ) / 3


        volume = df["volume"]


        price_range = np.linspace(
            prices.min(),
            prices.max(),
            bins
        )


        volume_profile = []


        for i in range(len(price_range)-1):

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