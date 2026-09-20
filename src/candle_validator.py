from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

INTERVAL_TIMEDELTAS: dict[str, pd.Timedelta] = {
    "1m": pd.Timedelta(minutes=1),
    "3m": pd.Timedelta(minutes=3),
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "2h": pd.Timedelta(hours=2),
    "4h": pd.Timedelta(hours=4),
    "6h": pd.Timedelta(hours=6),
    "8h": pd.Timedelta(hours=8),
    "12h": pd.Timedelta(hours=12),
    "1d": pd.Timedelta(days=1),
    "3d": pd.Timedelta(days=3),
    "1w": pd.Timedelta(weeks=1),
}


class ValidationError(ValueError):
    """Raised when strict validation fails on a candle dataset."""


@dataclass
class CandleQualityReport:
    total_candles: int = 0
    duplicates_dropped: int = 0
    gaps_count: int = 0
    missing_candles_estimated: int = 0
    gaps: list[dict] = field(default_factory=list)
    ohlcv_anomalies_count: int = 0
    is_clean: bool = True
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class CandleValidator:
    """Validates the continuity, chronological order, and OHLCV logic of candle datasets."""

    def __init__(self, default_interval: str = "1h"):
        self.default_interval = default_interval

    def validate(
        self,
        df: pd.DataFrame,
        interval: str | None = None,
        strict: bool = False,
        repair: bool = True,
    ) -> tuple[pd.DataFrame, CandleQualityReport]:
        """Validates and optionally repairs a candle DataFrame.

        Parameters:
        - df: Input OHLCV DataFrame
        - interval: Temporal resolution ('15m', '1h', '4h', etc.)
        - strict: If True, raises ValidationError on any gaps or anomalies
        - repair: If True, deduplicates and sorts timestamps
        """
        if df.empty:
            report = CandleQualityReport(total_candles=0, is_clean=True)
            return df.copy(), report

        target_interval = (interval or self.default_interval).strip().lower()
        if target_interval not in INTERVAL_TIMEDELTAS:
            raise ValueError(
                f"Intervalo '{target_interval}' no soportado. "
                f"Opciones válidas: {list(INTERVAL_TIMEDELTAS.keys())}"
            )

        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(f"Faltan columnas requeridas en el DataFrame: {sorted(missing_cols)}")

        data = df.copy()
        data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

        report = CandleQualityReport(total_candles=len(data))

        # 1. Finite and numeric values check
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        nan_mask = data[numeric_cols].isna().any(axis=1)
        if nan_mask.any():
            nan_count = int(nan_mask.sum())
            report.ohlcv_anomalies_count += nan_count
            report.details.append(f"{nan_count} filas contienen valores NaN o no numéricos.")
            if strict:
                raise ValidationError(f"Dataset contiene {nan_count} filas con valores NaN.")
            if repair:
                data = data[~nan_mask].copy()

        # 2. Duplicate detection & sorting
        dup_mask = data.duplicated(subset=["timestamp"], keep="last")
        dup_count = int(dup_mask.sum())

        if dup_count > 0:
            report.duplicates_dropped = dup_count
            report.details.append(f"{dup_count} velas duplicadas detectadas y descartadas.")
            if strict:
                raise ValidationError(f"Dataset contiene {dup_count} marcas de tiempo duplicadas.")
            if repair:
                data = data[~dup_mask].copy()

        # Chronological sort
        data = data.sort_values("timestamp").reset_index(drop=True)

        # 3. OHLC sanity checks
        if not data.empty:
            high_invalid = (data["high"] < data["open"] - 1e-9) | (
                data["high"] < data["close"] - 1e-9
            )
            low_invalid = (data["low"] > data["open"] + 1e-9) | (
                data["low"] > data["close"] + 1e-9
            )
            spread_invalid = data["high"] < data["low"] - 1e-9
            volume_negative = data["volume"] < 0

            anomalies = high_invalid | low_invalid | spread_invalid | volume_negative
            anomaly_count = int(anomalies.sum())

            if anomaly_count > 0:
                report.ohlcv_anomalies_count += anomaly_count
                report.details.append(
                    f"{anomaly_count} velas con inconsistencias lógicas de precios o volumen negativo."
                )
                if strict:
                    raise ValidationError(
                        f"Dataset contiene {anomaly_count} anomalías lógicas en precios OHLCV."
                    )
                if repair:
                    # Sanitize bounds
                    data["high"] = np.maximum(data["high"], np.maximum(data["open"], data["close"]))
                    data["low"] = np.minimum(data["low"], np.minimum(data["open"], data["close"]))
                    data["volume"] = np.maximum(data["volume"], 0.0)

        # 4. Gap Detection
        expected_step = INTERVAL_TIMEDELTAS[target_interval]
        if len(data) > 1:
            diffs = data["timestamp"].diff().iloc[1:]
            gap_mask = diffs > expected_step

            if gap_mask.any():
                gap_indices = gap_mask[gap_mask].index
                for idx in gap_indices:
                    prev_ts = data.loc[idx - 1, "timestamp"]
                    curr_ts = data.loc[idx, "timestamp"]
                    delta = curr_ts - prev_ts
                    missing_est = int(round(delta / expected_step)) - 1

                    gap_entry = {
                        "from": str(prev_ts),
                        "to": str(curr_ts),
                        "gap_duration": str(delta),
                        "missing_candles": max(1, missing_est),
                    }
                    report.gaps.append(gap_entry)
                    report.missing_candles_estimated += gap_entry["missing_candles"]

                report.gaps_count = len(report.gaps)
                report.details.append(
                    f"{report.gaps_count} huecos temporales detectados "
                    f"(~{report.missing_candles_estimated} velas faltantes)."
                )

                if strict:
                    raise ValidationError(
                        f"Se detectaron {report.gaps_count} huecos temporales en el dataset."
                    )

        report.total_candles = len(data)
        report.is_clean = (
            report.gaps_count == 0
            and report.duplicates_dropped == 0
            and report.ohlcv_anomalies_count == 0
        )

        return data, report
