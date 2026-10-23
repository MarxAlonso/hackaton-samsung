"""Paso 3 — Variables del modelo y objetivos.

Cada fila es (distrito, semana t) usando solo información disponible hasta t.
Objetivos: lo que ocurre en las semanas t+1 … t+4.

Brote de dengue = alguna semana futura supera el canal endémico (percentil 75 histórico
de la incidencia de esa semana del año en ese distrito, calculado solo con años de
entrenamiento) y tiene al menos 5 casos. Es el criterio de "zona de epidemia" del MINSA.
"""
import numpy as np
import pandas as pd

from config import DATA_PROCESSED, DISEASES, HORIZON_WEEKS, TRAIN_END, districts_frame

# Variables del modelo de dengue, en el orden exacto que espera el ONNX
DENGUE_FEATURES = [
    "rain_0_1", "rain_2_6", "rain_7_12", "tmean_0_3", "tmax_0", "humidity_0_3",
    "nino12", "oni", "inc_0", "inc_0_3", "inc_52", "canal_next",
    "altitude", "water_access", "log_pop", "week_sin", "week_cos",
]
# Variables que cambian en el simulador "¿y si llueve más?"
RAIN_FEATURES = ["rain_0_1", "rain_2_6", "rain_7_12"]
TEMP_FEATURES = ["tmean_0_3", "tmax_0"]

# Variables de los modelos simples (regresión logística) de las otras enfermedades.
# Sin índices de El Niño: hoy están fuera del rango de entrenamiento y la logística extrapolaría.
SIMPLE_FEATURES = [
    "rain_0_1", "rain_2_6", "tmax_0", "tmean_0_3", "tmean_change", "humidity_0_3",
    "water_access", "own_inc_0_3", "week_sin", "week_cos",
]


def _roll(g, col, window, shift=0, how="sum"):
    return g[col].transform(lambda s: getattr(s.shift(shift).rolling(window, min_periods=1), how)())


def base_table():
    climate = pd.read_parquet(DATA_PROCESSED / "climate_weekly.parquet")
    enso = pd.read_parquet(DATA_PROCESSED / "enso_weekly.parquet")
    cases = pd.read_parquet(DATA_PROCESSED / "cases_weekly.parquet")
    df = (climate.merge(enso, on="week", how="left")
          .merge(cases, on=["district_id", "week"])
          .merge(districts_frame(), on="district_id"))
    return df.sort_values(["district_id", "week"]).reset_index(drop=True)


def endemic_channel(df, disease="dengue", q=0.75):
    """Percentil histórico de la incidencia por distrito y semana del año (solo años de entrenamiento)."""
    train = df[df.week <= TRAIN_END].copy()
    train["epiweek"] = train.week.dt.isocalendar().week.astype(int).clip(upper=52)
    train["inc"] = train[disease] / train.population * 1e5
    rows = []
    for district_id, d in train.groupby("district_id"):
        for w in range(1, 53):
            near = [(w + k - 1) % 52 + 1 for k in (-2, -1, 0, 1, 2)]  # suaviza ±2 semanas
            rows.append((district_id, w, d[d.epiweek.isin(near)].inc.quantile(q)))
    return pd.DataFrame(rows, columns=["district_id", "epiweek", "canal"])


def add_features(df, channel):
    df = df.copy()
    g = df.groupby("district_id")
    df["rain_0_1"] = _roll(g, "rain_mm", 2)
    df["rain_2_6"] = _roll(g, "rain_mm", 5, shift=2)
    df["rain_7_12"] = _roll(g, "rain_mm", 6, shift=7)
    df["tmean_0_3"] = _roll(g, "tmean", 4, how="mean")
    df["tmax_0"] = df["tmax"]
    df["humidity_0_3"] = _roll(g, "humidity", 4, how="mean")
    df["tmean_change"] = g["tmean"].diff().abs()
    df["nino12"] = df["nino12_anom"]
    df["log_pop"] = np.log(df.population)
    epiweek = df.week.dt.isocalendar().week.astype(int).clip(upper=52)
    df["epiweek"] = epiweek
    df["week_sin"] = np.sin(2 * np.pi * epiweek / 52)
    df["week_cos"] = np.cos(2 * np.pi * epiweek / 52)

    per100k = 1e5 / df.population
    df["inc_0"] = df.dengue * per100k
    df["inc_0_3"] = _roll(g, "dengue", 4) * per100k
    df["inc_52"] = _roll(g, "dengue", 52) * per100k

    # Canal endémico de las próximas semanas (umbral de alerta) y objetivo de brote
    df = df.merge(channel, on=["district_id", "epiweek"], how="left")
    g = df.groupby("district_id")
    # El canal depende solo del calendario: se conoce para semanas futuras sin esperar datos
    canal_lookup = channel.set_index(["district_id", "epiweek"])["canal"]
    future_canal = []
    future_over = []
    for k in range(1, HORIZON_WEEKS + 1):
        epiweek_k = (df["epiweek"] - 1 + k) % 52 + 1
        canal_k = pd.Series(canal_lookup.reindex(list(zip(df.district_id, epiweek_k))).values, index=df.index)
        cases_k = g["dengue"].shift(-k)
        future_canal.append(canal_k)
        future_over.append((cases_k * per100k > canal_k) & (cases_k >= 5))
    df["canal_next"] = pd.concat(future_canal, axis=1).mean(axis=1)
    df["dengue_outbreak"] = pd.concat(future_over, axis=1).any(axis=1).astype(int)
    df["canal_now"] = df["canal"]

    # Casos futuros (t+1..t+4) de cada enfermedad
    for disease in DISEASES:
        future = sum(g[disease].shift(-k) for k in range(1, HORIZON_WEEKS + 1))
        df[f"{disease}_next"] = future
        df[f"{disease}_inc_0_3"] = _roll(g, disease, 4) * per100k
    return df


def build():
    df = base_table()
    channel = endemic_channel(df)
    feats = add_features(df, channel)
    return feats, channel


def complete_rows(df):
    """Filas con historia suficiente y futuro observado (para entrenar/evaluar)."""
    min_week = df.week.min() + pd.Timedelta(weeks=52)
    return df[(df.week >= min_week) & df["dengue_next"].notna()].dropna(subset=DENGUE_FEATURES)
