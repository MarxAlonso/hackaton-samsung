"""Paso 4b — Peligro de lluvias extremas (inundación y huaico).

No es un modelo entrenado con eventos etiquetados (no hay inventario público por distrito): es
un índice hidrometeorológico, el enfoque habitual de alertas por umbrales de lluvia.

  - Se acumula la lluvia de 3 días consecutivos.
  - Se compara con la historia del propio distrito (solo años de entrenamiento, <= TRAIN_END):
      · umbral MEDIO  = percentil 99   → lluvia intensa, encharcamientos probables.
      · umbral ALTO   = percentil 99,9 → lluvia comparable a los eventos del Niño costero
                                         de 2017 y 2023 en ese distrito.
  - Ventana: últimos 14 días observados + próximos 16 días de pronóstico (Open-Meteo).
    En los replays históricos solo se usan los 14 días observados (sin mirar el futuro).

Salida (lo consume export.py): umbrales por distrito y, por escenario, nivel + serie diaria.
"""
import numpy as np
import pandas as pd

from config import DATA_PROCESSED, DATA_RAW, TRAIN_END

LOOKBACK_DAYS = 14
P_MEDIO, P_ALTO = 0.99, 0.999


def load_daily():
    daily = pd.read_parquet(DATA_PROCESSED.parent / "raw" / "climate_daily.parquet")
    daily["time"] = pd.to_datetime(daily["time"])
    return daily


def rolling3(series):
    return series.rolling(3, min_periods=3).sum()


def thresholds(daily):
    """Umbrales por distrito con la historia de entrenamiento."""
    out = {}
    for did, g in daily.groupby("district_id"):
        g = g.sort_values("time").set_index("time")
        r3 = rolling3(g.precipitation_sum)
        train = r3[r3.index <= TRAIN_END].dropna()
        out[did] = {"medio": round(float(train.quantile(P_MEDIO)), 1),
                    "alto": round(float(train.quantile(P_ALTO)), 1)}
    return out


def backtest(daily, th):
    """Días-distrito sobre el umbral alto por año: debería destacar 2017 y 2023 (2023 no se vio al fijar el umbral)."""
    rows = []
    for did, g in daily.groupby("district_id"):
        g = g.sort_values("time").set_index("time")
        r3 = rolling3(g.precipitation_sum).dropna()
        hit = r3 >= th[did]["alto"]
        rows.append(hit.groupby(hit.index.year).sum())
    by_year = pd.concat(rows, axis=1).sum(axis=1)
    return {int(y): int(v) for y, v in by_year.items() if y >= 2015}


def snapshot(daily, forecast, th, obs_end, use_forecast):
    """Nivel de lluvia extrema por distrito para una fecha de corte (obs_end = último día observado)."""
    obs_end = pd.Timestamp(obs_end)
    start = obs_end - pd.Timedelta(days=LOOKBACK_DAYS - 1)
    result, series = {}, {}
    for did, g in daily.groupby("district_id"):
        g = g.sort_values("time").set_index("time").precipitation_sum
        obs = g[(g.index >= start - pd.Timedelta(days=2)) & (g.index <= obs_end)]
        obs_r3 = rolling3(obs)[start:]
        days = list(obs[start:].items())
        r3 = list(obs_r3.items())
        fc_days, fc_r3 = [], []
        if use_forecast and forecast is not None:
            f = forecast[forecast.district_id == did].sort_values("time").set_index("time").precipitation_sum
            f = f[f.index > obs_end]
            fc_days = list(f.items())
            fc_r3 = list(rolling3(f).dropna().items())
        t = th[did]
        every = r3 + fc_r3
        peak_date, peak = max(every, key=lambda kv: kv[1]) if every else (obs_end, 0.0)
        is_fc = peak_date > obs_end
        nivel = "alto" if peak >= t["alto"] else "medio" if peak >= t["medio"] else "bajo"
        result[did] = {
            "nivel": nivel,
            "lluvia_max_3d_mm": round(float(peak), 1),
            "fecha_max": peak_date.strftime("%Y-%m-%d"),
            "es_pronostico": bool(is_fc),
            "umbral_medio_mm": t["medio"], "umbral_alto_mm": t["alto"],
            "ratio_umbral_alto": round(float(peak / t["alto"]), 2),
            "lluvia_14d_mm": round(float(obs[start:].sum()), 1),
            "lluvia_pronostico_16d_mm": round(float(sum(v for _, v in fc_days)), 1) if fc_days else None,
            "con_pronostico": bool(use_forecast and fc_days),
        }
        all_days = days + fc_days
        r3_by_date = dict(r3 + fc_r3)
        series[did] = {
            "fechas": [d.strftime("%Y-%m-%d") for d, _ in all_days],
            "mm": [round(float(v), 1) for _, v in all_days],
            "r3": [round(float(r3_by_date.get(d, np.nan)), 1) if d in r3_by_date else None for d, _ in all_days],
            "n_obs": len(days),
        }
    return result, series


def load_forecast():
    path = DATA_PROCESSED / "forecast_daily.parquet"
    if not path.exists():
        return None
    f = pd.read_parquet(path)
    f["time"] = pd.to_datetime(f["time"])
    return f


if __name__ == "__main__":
    daily = load_daily()
    th = thresholds(daily)
    print("Umbrales (mm en 3 días), muestra:")
    for did in ("piu-piura", "lam-chiclayo", "tum-tumbes", "piu-ayabaca"):
        print(f"  {did:14s} medio {th[did]['medio']:6.1f}  alto {th[did]['alto']:6.1f}")
    print("Días-distrito sobre umbral alto por año:", backtest(daily, th))
    fc = load_forecast()
    res, _ = snapshot(daily, fc, th, daily.time.max(), True)
    from collections import Counter
    print("Hoy:", Counter(v["nivel"] for v in res.values()), "| ventana hasta", daily.time.max().date())
    for week, label in (("2017-04-10", "2017"), ("2023-04-24", "2023")):
        res, _ = snapshot(daily, None, th, pd.Timestamp(week) + pd.Timedelta(days=6), False)
        print(label, Counter(v["nivel"] for v in res.values()))
