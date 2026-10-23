"""Paso 2 — Simulación de casos semanales por distrito, anclada al clima REAL.

Las bases del hackathon permiten datos simulados. Los casos reales por distrito y semana
del CDC-MINSA se publican principalmente en PDF; por eso simulamos con mecanismos
epidemiológicos conocidos y el clima observado de Open-Meteo/NOAA:

- Dengue: modelo de renovación (contagio semana a semana). La lluvia de 2 a 6 semanas
  atrás crea criaderos del Aedes aegypti, la temperatura acelera el ciclo, la altitud
  lo limita (>2000 m casi no hay vector) y los hogares sin agua por red la almacenan
  en recipientes (criadero permanente). La inmunidad tras un brote frena el siguiente.
- Leptospirosis: lluvias intensas e inundaciones (contacto con agua estancada).
- EDA: calor + falta de agua segura + inundaciones que dañan el saneamiento.
- Golpe de calor: temperatura máxima extrema.
- IRA: cambios bruscos de temperatura y semanas frías.

Salida: data/processed/cases_weekly.parquet
"""
import zlib

import numpy as np
import pandas as pd

from config import DATA_PROCESSED, SEED, districts_frame


def rng_for(district_id, stream):
    """Generador propio por (distrito, propósito). Así, al agregar semanas nuevas al final,
    las semanas ya simuladas NO cambian: el pasado es estable entre reentrenamientos."""
    return np.random.default_rng([SEED, zlib.crc32(district_id.encode()), zlib.crc32(stream.encode())])


def negbin(rng, mean, k):
    """Conteo con sobre-dispersión (binomial negativa = mezcla gamma-Poisson), típico de datos
    epidemiológicos. Una sola llamada por elemento, para que el flujo aleatorio sea estable."""
    mean = np.maximum(mean, 1e-9)
    return rng.negative_binomial(k, k / (k + mean))


def climate_table():
    climate = pd.read_parquet(DATA_PROCESSED / "climate_weekly.parquet")
    enso = pd.read_parquet(DATA_PROCESSED / "enso_weekly.parquet")
    df = climate.merge(enso, on="week", how="left").merge(districts_frame(), on="district_id")
    df = df.sort_values(["district_id", "week"]).reset_index(drop=True)
    g = df.groupby("district_id")
    df["rain_2_6"] = g["rain_mm"].transform(lambda s: s.shift(2).rolling(5, min_periods=1).sum()).fillna(0)
    df["rain_0_2"] = g["rain_mm"].transform(lambda s: s.rolling(3, min_periods=1).sum())
    df["tmean_lag"] = g["tmean"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean()).bfill()
    df["tmean_change"] = g["tmean"].diff().abs().fillna(0)
    return df


def altitude_suitability(alt):
    return np.where(alt < 1000, 1.0, np.where(alt < 2000, 0.35, 0.03))


def simulate_dengue(df):
    """Modelo de renovación por distrito: casos_t = importación + R_t · casos recientes."""
    out = np.zeros(len(df), dtype=int)
    gen_weights = np.array([0.35, 0.45, 0.20])  # intervalo serial ~2 semanas
    for did, idx in df.groupby("district_id").indices.items():
        d = df.iloc[idx]
        pop = d.population.iloc[0]
        water = d.water_access.iloc[0]
        s_alt = altitude_suitability(d.altitude.iloc[0])
        temp_f = np.exp(-((d.tmean_lag.values - 28.0) / 4.5) ** 2)
        rain_f = 1 - np.exp(-d.rain_2_6.values / 70.0)
        storage = 0.25 + 0.55 * (1 - water)  # agua almacenada en baldes/tanques
        # Factores no observados: fumigaciones, recojo de inservibles, microclima
        shocks = rng_for(did, "dengue-shocks").lognormal(0, 0.25, len(d))
        rng = rng_for(did, "dengue-cases")
        breeding = s_alt * temp_f * (storage + 1.7 * rain_f) * shocks
        nino = np.clip(d.nino12_anom.fillna(0).values, 0, None)
        r0 = 1.85 * rng_for(did, "dengue-r0").lognormal(0, 0.08)
        cases = np.zeros(len(d))
        for t in range(len(d)):
            recent = cases[max(0, t - 3):t][::-1]
            pressure = (recent * gen_weights[:len(recent)]).sum()
            cum52 = cases[max(0, t - 52):t].sum()
            susceptible = max(0.05, 1 - cum52 / (pop * 0.10))
            r_t = r0 * breeding[t] * susceptible * (1 + 0.06 * nino[t])
            imported = pop / 1e5 * 0.12 * breeding[t]
            cases[t] = negbin(rng, imported + r_t * pressure, k=6)
        # Subregistro: solo una parte de las infecciones llega a notificarse, y varía por semana
        report_rate = np.clip(0.55 * rng_for(did, "dengue-report").lognormal(0, 0.3, len(d)), 0.15, 0.95)
        out[idx] = rng_for(did, "dengue-notify").binomial(cases.astype(int), report_rate)
    return out


def simulate_simple(df):
    """Las otras 4 enfermedades, distrito por distrito (cada una con su propio flujo aleatorio)."""
    parts = [simulate_simple_district(did, df.iloc[idx]) for did, idx in df.groupby("district_id").indices.items()]
    out = {k: np.zeros(len(df), dtype=int) for k in parts[0][1]}
    for (idx, res) in parts:
        for k, v in res.items():
            out[k][idx] = v
    return out


def simulate_simple_district(did, df):
    idx = df.index.values
    pop100k = df.population.values / 1e5
    flood = (df.rain_mm.values > 40).astype(float)
    flood_prev = df.groupby("district_id")["rain_mm"].shift(1).fillna(0).values > 40
    rain_f = 1 - np.exp(-df.rain_0_2.values / 90.0)
    no_water = 1 - df.water_access.values
    district_effect = rng_for(did, "effect").normal(0, 0.12)
    week = df.week.dt.isocalendar().week.values.astype(float)
    cold_season = np.cos(2 * np.pi * (week - 30) / 52)  # pico en invierno (jul-ago)

    lepto = pop100k * np.exp(-1.2 + 2.0 * rain_f + 0.9 * flood + district_effect)
    eda = pop100k * np.exp(3.55 + 0.07 * (df.tmax.values - 30) + 1.0 * no_water
                           + 0.45 * flood_prev + district_effect)
    heat = pop100k * np.exp(-2.2 + 0.55 * np.clip(df.tmax.values - 30, 0, None) + district_effect)
    ira = pop100k * np.exp(4.6 + 0.35 * df.tmean_change.values + 0.25 * cold_season
                           + 0.04 * np.clip(22 - df.tmean.values, 0, None) + district_effect)
    return idx, {
        "leptospirosis": negbin(rng_for(did, "lepto"), lepto, k=4),
        "eda": negbin(rng_for(did, "eda"), eda, k=15),
        "golpe_calor": negbin(rng_for(did, "heat"), heat, k=4),
        "ira": negbin(rng_for(did, "ira"), ira, k=20),
    }


def main():
    df = climate_table()
    df["dengue"] = simulate_dengue(df)
    for name, values in simulate_simple(df).items():
        df[name] = values
    cols = ["district_id", "week", "dengue", "leptospirosis", "eda", "golpe_calor", "ira"]
    df[cols].to_parquet(DATA_PROCESSED / "cases_weekly.parquet", index=False)

    yearly = df.assign(year=df.week.dt.year).groupby("year")[cols[2:]].sum()
    print("Casos simulados por año (47 distritos):")
    print(yearly.to_string())
    top = (df[df.week.dt.year == 2023].groupby("district_id").dengue.sum()
           .sort_values(ascending=False).head(5))
    print("\nDistritos con más dengue en 2023:\n" + top.to_string())


if __name__ == "__main__":
    main()
