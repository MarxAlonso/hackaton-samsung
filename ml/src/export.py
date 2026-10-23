"""Paso 5 — Exporta predicciones y modelos para la web (Astro) y la API (FastAPI).

Genera:
  web/public/data/app.json      → distritos, escenarios, predicciones, historia, métricas, textos
  web/public/models/*.onnx      → modelos de dengue para el simulador "¿y si llueve más?"
  api/models/                   → modelo joblib + app.json para el endpoint /predict

Escenarios:
  - "actual": la última semana con clima observado.
  - "2023" y "2017": semanas previas a las grandes epidemias, para mostrar qué habría
    anticipado el sistema (el modelo no vio 2023 al entrenar).
"""
import json
import math
import shutil

import joblib
import numpy as np
import pandas as pd

from config import (API_MODELS, DATA_PROCESSED, DISEASES, HORIZON_WEEKS, MODELS, REPORTS,
                    WEB_DATA, districts_frame)
from content import (AUTHORITY_ACTIONS, CITIZEN_ACTIONS, DISEASE_INFO, LEVEL_THRESHOLDS, LEVELS,
                     level_of)
from content import FLOOD_ACTIONS_AUTHORITY, FLOOD_ACTIONS_CITIZEN, FLOOD_INFO
from features import DENGUE_FEATURES, RAIN_FEATURES, SIMPLE_FEATURES, TEMP_FEATURES
import hazards

HISTORY_WEEKS = 40


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def simple_proba(model, row):
    z = model["intercept"]
    for f, mu, sd, c in zip(model["features"], model["mean"], model["scale"], model["coef"]):
        z += c * (row[f] - mu) / sd
    return sigmoid(z)


LEVEL_ORDER = {"alto": 2, "medio": 1, "bajo": 0}


def rank_risks(risks, base_rates):
    """Primero el nivel; luego el riesgo relativo (prob / frecuencia normal) para mostrar lo inusual."""
    return sorted(risks, key=lambda k: (-LEVEL_ORDER[risks[k]["nivel"]], -risks[k]["prob"] / base_rates[k]))


def confidence(p10, p50, p90, prob):
    """Confianza en lenguaje simple: rango estrecho y probabilidad lejos del 50% = alta."""
    spread = (p90 - p10) / (p50 + 10)
    certainty = abs(prob - 0.5) * 2
    score = 0.6 * certainty + 0.4 * max(0.0, 1 - spread / 3)
    label = "alta" if score >= 0.6 else "media" if score >= 0.35 else "baja"
    return label, round(score, 2)


def epidemic_weeks(feats, year):
    """Semana de referencia: ~3 semanas antes del pico regional de dengue de ese año."""
    weekly = feats[feats.week.dt.year == year].groupby("week").dengue.sum()
    return weekly.idxmax() - pd.Timedelta(weeks=3)


def predict_snapshot(feats, week, bundle, simple_models, districts):
    rows = feats[feats.week == week].set_index("district_id")
    X = rows[DENGUE_FEATURES].values
    prob = bundle["clf"].predict_proba(X)[:, 1]
    q = {k: np.expm1(r.predict(X)).clip(min=0) for k, r in bundle["regs"].items()}
    q = dict(zip(("p10", "p50", "p90"), np.sort(np.vstack([q["p10"], q["p50"], q["p90"]]), axis=0)))
    out = []
    for i, (district_id, row) in enumerate(rows.iterrows()):
        values = {f: round(float(row[f]), 4) for f in DENGUE_FEATURES + ["tmean_change"]}
        for disease in DISEASES:
            values[f"{disease}_inc_0_3"] = round(float(np.log1p(row[f"{disease}_inc_0_3"])), 4)
        p10, p50, p90 = (float(q[k][i]) for k in ("p10", "p50", "p90"))
        conf_label, conf_score = confidence(p10, p50, p90, float(prob[i]))
        risks = {"dengue": {
            "prob": round(float(prob[i]), 3),
            "casos_p10": round(p10), "casos_p50": round(p50), "casos_p90": round(p90),
            "confianza": conf_label, "confianza_score": conf_score,
        }}
        for disease, model in simple_models.items():
            feat_row = {**values, "own_inc_0_3": values[f"{disease}_inc_0_3"]}
            risks[disease] = {"prob": round(simple_proba(model, feat_row), 3)}
        for disease, r in risks.items():
            r["nivel"] = level_of(r["prob"])
        base_rates = {"dengue": bundle["base_rate"], **{k: m["base_rate"] for k, m in simple_models.items()}}
        top = rank_risks(risks, base_rates)
        out.append({
            "district_id": district_id,
            "features": values,
            "riesgos": risks,
            "nivel": risks[top[0]]["nivel"],
            "top_riesgos": top[:3],
            "recursos": {"pruebas": math.ceil(p90 * 1.5), "camas": math.ceil(p90 * 0.04)},
            "clima": {"lluvia_ultimas_2sem": round(float(row.rain_0_1), 1),
                      "lluvia_2_a_6sem": round(float(row.rain_2_6), 1),
                      "tmax": round(float(row.tmax_0), 1),
                      "tmedia": round(float(row.tmean_0_3), 1)},
        })
    return out


def history(feats, week, districts, include_future):
    end = week + pd.Timedelta(weeks=HORIZON_WEEKS if include_future else 0)
    start = week - pd.Timedelta(weeks=HISTORY_WEEKS)
    h = feats[(feats.week > start) & (feats.week <= end)]
    out = {}
    for district_id, d in h.groupby("district_id"):
        pop = districts.loc[district_id, "population"]
        out[district_id] = {
            "semanas": d.week.dt.strftime("%Y-%m-%d").tolist(),
            "dengue": d.dengue.astype(int).tolist(),
            "canal": (d.canal_now * pop / 1e5).round(1).fillna(0).tolist(),
            "lluvia": d.rain_mm.round(1).tolist(),
        }
    return out


def scenario_reference(feats):
    """Clima de referencia para el simulador: la semana más lluviosa del verano 2023 por distrito."""
    summer = feats[(feats.week >= "2023-01-01") & (feats.week <= "2023-05-31")]
    ref = {}
    for district_id, d in summer.groupby("district_id"):
        row = d.loc[d.rain_2_6.idxmax()]
        ref[district_id] = {f: round(float(row[f]), 2) for f in RAIN_FEATURES + TEMP_FEATURES}
    return ref


def forecast_summary():
    path = DATA_PROCESSED / "forecast_daily.parquet"
    if not path.exists():
        return {}
    fc = pd.read_parquet(path)
    return {d: {"lluvia_16d": round(float(g.precipitation_sum.sum()), 1),
                "tmax_16d": round(float(g.temperature_2m_max.max()), 1),
                "desde": g.time.min().strftime("%Y-%m-%d"), "hasta": g.time.max().strftime("%Y-%m-%d")}
            for d, g in fc.groupby("district_id")}


def export_series(feats, districts):
    """Serie semanal completa por distrito (casos, umbral, lluvia, tmax) para mapa de calor y comparaciones."""
    weeks = sorted(feats.week.unique())
    out = {"semanas": [pd.Timestamp(w).strftime("%Y-%m-%d") for w in weeks], "distritos": {}}
    for district_id, d in feats.groupby("district_id"):
        d = d.set_index("week").reindex(weeks)
        pop = districts.loc[district_id, "population"]
        out["distritos"][district_id] = {
            "dengue": d.dengue.fillna(0).astype(int).tolist(),
            "inc": (d.dengue.fillna(0) / pop * 1e5).round(1).tolist(),
            "canal": (d.canal_now * pop / 1e5).round(1).fillna(0).tolist(),
            "lluvia": d.rain_mm.round(1).fillna(0).tolist(),
            "tmax": d.tmax.round(1).fillna(0).tolist(),
        }
    return out


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main():
    feats = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    feats = feats.dropna(subset=DENGUE_FEATURES)
    eval_bundle = joblib.load(MODELS / "dengue.joblib")
    # Hoy se predice con el modelo de producción (el que ganó el reentrenamiento); los replays
    # con el de evaluación, que nunca vio 2023.
    prod_path = MODELS / "dengue_prod.joblib"
    prod_bundle = joblib.load(prod_path) if prod_path.exists() else eval_bundle
    bundle = eval_bundle
    daily = hazards.load_daily()
    flood_th = hazards.thresholds(daily)
    forecast = hazards.load_forecast()
    simple_models = json.loads((MODELS / "simple_models.json").read_text(encoding="utf-8"))
    metrics = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))
    districts = districts_frame().set_index("district_id")
    enso = pd.read_parquet(DATA_PROCESSED / "enso_weekly.parquet").set_index("week")

    snapshots_def = [
        ("actual", "Hoy", feats.week.max(), False),
        ("2023", "Verano 2023 (Ciclón Yaku + Niño costero)", epidemic_weeks(feats, 2023), True),
        ("2017", "Verano 2017 (Niño costero)", epidemic_weeks(feats, 2017), True),
    ]
    snapshots = {}
    for key, label, week, future in snapshots_def:
        is_now = key == "actual"
        use = prod_bundle if is_now else eval_bundle
        preds = predict_snapshot(feats, week, use, simple_models, districts)
        # Lluvias extremas: hoy = últimos 14 días observados + 16 de pronóstico; replay = solo lo observado hasta esa semana
        obs_end = daily.time.max() if is_now else week + pd.Timedelta(days=6)
        flood, flood_series = hazards.snapshot(daily, forecast, flood_th, obs_end, use_forecast=is_now)
        for p in preds:
            p["inundacion"] = flood[p["district_id"]]
        snapshots[key] = {
            "etiqueta": label,
            "semana": week.strftime("%Y-%m-%d"),
            "nino12": round(float(enso.loc[week, "nino12_anom"]), 2),
            "oni": round(float(enso.loc[week, "oni"]), 2),
            "modelo": {"id": "prod" if is_now else "eval", "origen": use.get("origen", "campeón de evaluación"),
                       "entrenado_hasta": use.get("entrenado_hasta", "2021-12-27")},
            "ventana_lluvia": {"hasta": obs_end.strftime("%Y-%m-%d"), "con_pronostico": is_now and forecast is not None},
            "distritos": preds,
            "historia": history(feats, week, districts, include_future=future),
            "inundacion_serie": flood_series,
        }
        n_high = sum(p["riesgos"]["dengue"]["nivel"] == "alto" for p in preds)
        print(f"  {key}: semana {week.date()} — {n_high} distritos en riesgo alto de dengue")

    app = {
        "generado": pd.Timestamp.now(tz="America/Lima").strftime("%Y-%m-%d %H:%M"),
        "horizonte_semanas": HORIZON_WEEKS,
        "distritos": districts.reset_index().to_dict(orient="records"),
        "escenarios": snapshots,
        "referencia_2023": scenario_reference(feats),
        "pronostico": forecast_summary(),
        "modelo": {
            "dengue_features": DENGUE_FEATURES,
            "rain_features": RAIN_FEATURES,
            "temp_features": TEMP_FEATURES,
            "simple_features": SIMPLE_FEATURES,
            "simples": {k: {kk: vv for kk, vv in v.items() if kk != "threshold_by_district"}
                        for k, v in simple_models.items()},
            "umbrales_nivel": LEVEL_THRESHOLDS,
            "tasa_base": {"dengue": eval_bundle["base_rate"], **{k: v["base_rate"] for k, v in simple_models.items()}},
        },
        "lluvias_extremas": {
            "metodo": "Lluvia acumulada en 3 días contra la historia del propio distrito (2015–2021): medio = percentil 99, alto = percentil 99,9.",
            "dias_distrito_sobre_umbral_alto_por_anio": hazards.backtest(daily, flood_th),
            "umbrales_mm": flood_th,
        },
        "monitoreo": read_json(REPORTS / "monitoring.json"),
        "reentrenamiento": read_json(REPORTS / "retrain.json"),
        "metricas": metrics,
        "contenido": {"enfermedades": DISEASE_INFO, "ciudadano": CITIZEN_ACTIONS,
                      "autoridad": AUTHORITY_ACTIONS, "niveles": LEVELS,
                      "lluvia_extrema": {"info": FLOOD_INFO, "ciudadano": FLOOD_ACTIONS_CITIZEN, "autoridad": FLOOD_ACTIONS_AUTHORITY}},
    }

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(app, ensure_ascii=False, separators=(",", ":"))
    (WEB_DATA / "app.json").write_text(payload, encoding="utf-8")
    series = json.dumps(export_series(feats, districts), ensure_ascii=False, separators=(",", ":"))
    (WEB_DATA / "series.json").write_text(series, encoding="utf-8")
    print(f"Exportado series.json ({len(series) / 1024:.0f} KB)")
    web_models = WEB_DATA.parent / "models"
    web_models.mkdir(exist_ok=True)
    for f in MODELS.glob("*.onnx"):
        shutil.copy(f, web_models / f.name)

    API_MODELS.mkdir(parents=True, exist_ok=True)
    shutil.copy(MODELS / "dengue.joblib", API_MODELS / "dengue.joblib")
    if prod_path.exists():
        shutil.copy(prod_path, API_MODELS / "dengue_prod.joblib")
    (API_MODELS / "app.json").write_text(payload, encoding="utf-8")
    print(f"Exportado app.json ({len(payload) / 1024:.0f} KB) y {len(list(MODELS.glob('*.onnx')))} modelos ONNX")


if __name__ == "__main__":
    main()
