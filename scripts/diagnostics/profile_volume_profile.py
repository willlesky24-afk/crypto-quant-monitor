"""
Script de diagnóstico y profiling para VolumeProfile.
Mide el tiempo de ejecución, uso de memoria y cuellos de botella en el cálculo
del perfil de volumen sobre datasets de diversos tamaños (100, 1000, 10000, 50000 velas).
"""
from __future__ import annotations

import cProfile
import io
import pstats
import time
import tracemalloc

import _bootstrap  # noqa: F401
import numpy as np
import pandas as pd

from src.volume_profile import VolumeProfile


def generate_benchmark_candles(n_candles: int = 10000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base_price = 50000.0
    returns = rng.normal(0.0001, 0.01, size=n_candles)
    close_prices = base_price * np.cumprod(1 + returns)
    high_prices = close_prices * (1 + rng.uniform(0.0, 0.005, size=n_candles))
    low_prices = close_prices * (1 - rng.uniform(0.0, 0.005, size=n_candles))
    open_prices = (high_prices + low_prices) / 2
    volumes = rng.uniform(10.0, 500.0, size=n_candles)

    timestamps = pd.date_range("2023-01-01", periods=n_candles, freq="1h")
    return pd.DataFrame(
        {
            "open_time": timestamps,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        }
    )


def run_profiling():
    print("=" * 70)
    print("PROFILING DE RENDIMIENTO: VolumeProfile.calculate")
    print("=" * 70)

    dataset_sizes = [100, 1000, 10000, 50000]
    vp = VolumeProfile()

    for n in dataset_sizes:
        df = generate_benchmark_candles(n)
        iterations = 50 if n <= 1000 else (10 if n <= 10000 else 3)

        tracemalloc.start()
        start_time = time.perf_counter()

        for _ in range(iterations):
            result = vp.calculate(df, bins=24)

        elapsed = (time.perf_counter() - start_time) / iterations
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n--- Dataset: {n:,} velas (Promedio de {iterations} iteraciones) ---")
        print(f"  Tiempo por cálculo:  {elapsed * 1000:.3f} ms ({elapsed:.6f} s)")
        print(f"  Memoria pico:        {peak_mem / 1024:.2f} KB")
        print(f"  Resultado obtenido:  POC={result['poc']}, VAH={result['vah']}, VAL={result['val']}")

    # cProfile detallado sobre 10,000 velas
    print("\n" + "=" * 70)
    print("DETALLE DE CUELLO DE BOTELLA (cProfile sobre 10,000 velas, 50 llamadas)")
    print("=" * 70)

    df_10k = generate_benchmark_candles(10000)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(50):
        vp.calculate(df_10k, bins=24)
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(15)
    print(s.getvalue())


if __name__ == "__main__":
    run_profiling()
