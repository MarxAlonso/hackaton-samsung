"""Simulación de casos SOLO para el golpe de calor.

Hasta ahora los casos de las 5 enfermedades eran simulados. Ahora dengue, diarreas (EDA), infecciones
respiratorias (IRA) y leptospirosis son datos REALES del CDC-MINSA (ver real_cases.py). El golpe de calor
no tiene una fuente abierta equivalente, así que sigue simulándose a partir de la temperatura máxima
real (Open-Meteo): más casos cuando pasa de ~30 °C, con ruido propio de cada distrito.

Cada distrito tiene su propio flujo aleatorio (semilla + distrito + propósito): al agregar semanas
nuevas, las ya simuladas no cambian.
"""
import zlib

import numpy as np
import pandas as pd

from config import DATA_PROCESSED, SEED, districts_frame


def rng_for(district_id, stream):
    return np.random.default_rng([SEED, zlib.crc32(district_id.encode()), zlib.crc32(stream.encode())])


def negbin(rng, mean, k):
    """Conteo con sobre-dispersión (binomial negativa); una llamada por elemento para un flujo estable."""
    mean = np.maximum(mean, 1e-9)
    return rng.negative_binomial(k, k / (k + mean))


def climate_table():
    climate = pd.read_parquet(DATA_PROCESSED / "climate_weekly.parquet")
    df = climate.merge(districts_frame(), on="district_id")
    return df.sort_values(["district_id", "week"]).reset_index(drop=True)


def simulate_heat(df):
    """Casos semanales simulados de golpe de calor (vector alineado con `df`)."""
    out = np.zeros(len(df), dtype=int)
    for did, idx in df.groupby("district_id").indices.items():
        d = df.iloc[idx]
        effect = rng_for(did, "effect").normal(0, 0.12)
        mean = d.population.values / 1e5 * np.exp(-2.2 + 0.55 * np.clip(d.tmax.values - 30, 0, None) + effect)
        out[idx] = negbin(rng_for(did, "heat"), mean, k=4)
    return out
