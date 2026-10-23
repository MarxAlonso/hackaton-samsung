"""Calibración de la intensidad y datos de incertidumbre (intervalos de confianza) de las métricas.

Problema medido: el modelo ordena bien los distritos pero subestima la intensidad de las epidemias grandes
(con casos recientes, lo observado fue 1,45 veces lo previsto en 2023 y 1,81 veces en 2024).

Corrección ("factor de intensidad"): en cada semana t se compara lo que realmente pasó con lo que el modelo
había previsto en las últimas W semanas CUYO RESULTADO YA SE CONOCE (las que terminaron 4 o más semanas antes
de t). La razón entre ambos, acotada, reescala los casos esperados (P10, P50 y P90). Solo usa información que
existía en t, y solo se aplica al modelo con casos recientes, porque necesita resultados recientes para calcularse.
Con el modelo de solo clima no hay resultados recientes y no se aplica.
"""
import numpy as np
import pandas as pd

WINDOW_WEEKS = 4   # semanas con resultado conocido que se comparan
LAG_WEEKS = 4      # un resultado se conoce 4 semanas después (horizonte de la predicción)
FACTOR_MIN, FACTOR_MAX = 0.5, 2.0
SMOOTH = 5         # casos de "ancla" para que semanas casi sin casos no muevan el factor


def weekly_sums(week, observed, predicted):
    """Casos observados y previstos (P50) sumados por semana, solo con las filas de resultado conocido."""
    df = pd.DataFrame({"week": week, "y": observed, "p": predicted}).dropna()
    g = df.groupby("week")[["y", "p"]].sum()
    return g.y, g.p


def intensity_factor(obs_by_week, pred_by_week, week):
    """Factor para la semana `week`, con lo que ya se sabía ese día."""
    known = obs_by_week.index[obs_by_week.index <= pd.Timestamp(week) - pd.Timedelta(weeks=LAG_WEEKS)][-WINDOW_WEEKS:]
    if len(known) == 0:
        return 1.0
    f = (obs_by_week.loc[known].sum() + SMOOTH) / (pred_by_week.loc[known].sum() + SMOOTH)
    return float(np.clip(f, FACTOR_MIN, FACTOR_MAX))


def factors_by_week(obs_by_week, pred_by_week, weeks):
    return {w: intensity_factor(obs_by_week, pred_by_week, w) for w in weeks}


def calibration_report(test, preds, obs_by_week, pred_by_week):
    """Antes y después de la corrección, por año de prueba: sesgo (observado/previsto), error y cobertura del rango."""
    f = test.week.map(factors_by_week(obs_by_week, pred_by_week, sorted(test.week.unique()))).values
    y = test.dengue_next.values
    rows = []
    for year in sorted(test.week.dt.year.unique()):
        m = (test.week.dt.year == year).values
        before = {k: preds[k][m] for k in ("p10", "p50", "p90")}
        after = {k: preds[k][m] * f[m] for k in ("p10", "p50", "p90")}
        rows.append({
            "anio": int(year),
            "razon_observado_previsto_antes": round(float(y[m].sum() / max(before["p50"].sum(), 1)), 2),
            "razon_observado_previsto_despues": round(float(y[m].sum() / max(after["p50"].sum(), 1)), 2),
            "cobertura_p10_p90_antes": round(float(((y[m] >= before["p10"]) & (y[m] <= before["p90"])).mean()), 3),
            "cobertura_p10_p90_despues": round(float(((y[m] >= after["p10"]) & (y[m] <= after["p90"])).mean()), 3),
        })
    total = {
        "mae_p50_antes": round(float(np.abs(y - preds["p50"]).mean()), 2),
        "mae_p50_despues": round(float(np.abs(y - preds["p50"] * f).mean()), 2),
        "cobertura_p10_p90_antes": round(float(((y >= preds["p10"]) & (y <= preds["p90"])).mean()), 3),
        "cobertura_p10_p90_despues": round(float(((y >= preds["p10"] * f) & (y <= preds["p90"] * f)).mean()), 3),
    }
    return {"regla": f"razón entre lo observado y lo previsto en las últimas {WINDOW_WEEKS} semanas con resultado conocido, "
                     f"acotada a {FACTOR_MIN}–{FACTOR_MAX} veces", "por_anio": rows, "total": total}


def bootstrap_by_district(test, stats, n_boot=300, seed=7):
    """Intervalo de confianza del 95% remuestreando DISTRITOS (no filas): las semanas de un mismo distrito se parecen
    mucho entre sí, así que remuestrear filas daría intervalos demasiado estrechos.
    `stats(df)` devuelve un dict de métricas."""
    rng = np.random.default_rng(seed)
    groups = {d: g for d, g in test.groupby("district_id")}
    ids = np.array(list(groups))
    draws = []
    for _ in range(n_boot):
        pick = rng.choice(ids, size=len(ids), replace=True)
        sample = pd.concat([groups[d] for d in pick], ignore_index=True)
        try:
            draws.append(stats(sample))
        except ValueError:  # una muestra sin brotes o sin semanas sin brote no tiene AUC
            continue
    out = {}
    for key in draws[0]:
        v = np.array([d[key] for d in draws], dtype=float)
        v = v[~np.isnan(v)]
        out[key] = [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
    out["_n_remuestreos"] = len(draws)
    return out
