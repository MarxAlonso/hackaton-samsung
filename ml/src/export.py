"""Paso 8 — Exporta predicciones y modelos para la web (Astro) y la API (FastAPI).

Genera:
  web/public/data/app.json      → distritos, escenarios, predicciones, métricas, textos y fuentes de datos
  web/public/data/series.json   → serie semanal por distrito (casos reales, umbral de brote, lluvia, temperatura)
  web/public/models/*.onnx      → modelos de dengue para el simulador "¿y si llueve más?"
  api/models/                   → modelos joblib + app.json para el endpoint /predict

Escenarios:
  - "actual": la última semana con clima observado. Los casos oficiales llegan con meses de retraso, así que
    cada distrito usa el modelo "con casos" solo si su último caso conocido es reciente (≤ 2 semanas);
    si no, usa el modelo "solo clima" y se avisa con claridad.
  - "2023" y "2017": semanas previas a las grandes epidemias, con casos reales. Muestran qué habría
    anticipado el sistema y qué pasó de verdad (el modelo de evaluación no vio 2022 en adelante al entrenar).
"""
import json
import math
import shutil

import joblib
import numpy as np
import pandas as pd

import hazards
from config import (API_MODELS, DATA_PROCESSED, DISEASES, HORIZON_WEEKS, MODELS, REPORTS,
                    WEB_DATA, districts_frame)
from content import (AUTHORITY_ACTIONS, CITIZEN_ACTIONS, DISEASE_INFO, FLOOD_ACTIONS_AUTHORITY,
                     FLOOD_ACTIONS_CITIZEN, FLOOD_INFO, LEVEL_THRESHOLDS, LEVELS, level_of)
from features import CLIMATE_FEATURES, DENGUE_FEATURES, FEATURES, RAIN_FEATURES, SIMPLE_FEATURES, TEMP_FEATURES
from retrain import PROD_FILE
from train import FAMILY_FILE, predict_cases

FRESH_DAYS = 14  # el último caso conocido debe ser de las últimas 2 semanas para usar el modelo "con casos"
LEVEL_ORDER = {"alto": 2, "medio": 1, "bajo": 0}


def num(x, nd=4):
    return None if pd.isna(x) else round(float(x), nd)


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def simple_proba(model, row):
    z = model["intercept"]
    for f, mu, sd, c in zip(model["features"], model["mean"], model["scale"], model["coef"]):
        z += c * (row[f] - mu) / sd
    return sigmoid(z)


def rank_risks(risks, base_rates):
    """Primero el nivel; luego el riesgo relativo (prob / frecuencia normal) para mostrar lo inusual."""
    return sorted(risks, key=lambda k: (-LEVEL_ORDER[risks[k]["nivel"]], -risks[k]["prob"] / base_rates[k]))


def confidence(p10, p50, p90, prob, family):
    """Confianza en lenguaje simple: rango estrecho y probabilidad lejos del 50% = alta.
    Sin casos recientes ("clima") nunca pasa de media: la evaluación muestra que ese modelo ordena bien
    los distritos pero calcula mal cuántos casos habrá."""
    spread = (p90 - p10) / (p50 + 10)
    certainty = abs(prob - 0.5) * 2
    score = 0.6 * certainty + 0.4 * max(0.0, 1 - spread / 3)
    label = "alta" if score >= 0.6 else "media" if score >= 0.35 else "baja"
    if family == "clima":
        label = "baja" if label == "baja" else "media"
        score = min(score, 0.5)
    return label, round(score, 2)


def epidemic_weeks(feats, year):
    """Semana de referencia: ~3 semanas antes del pico regional de dengue de ese año."""
    weekly = feats[feats.week.dt.year == year].groupby("week").dengue.sum()
    return weekly.idxmax() - pd.Timedelta(weeks=3)


def load_bundles():
    out = {}
    for fam in FEATURES:
        evaluation = joblib.load(MODELS / FAMILY_FILE[fam])
        prod_path = MODELS / PROD_FILE[fam]
        out[("eval", fam)] = evaluation
        out[("prod", fam)] = joblib.load(prod_path) if prod_path.exists() else evaluation
    return out


def predict_snapshot(feats, week, model_id, bundles, simple_models, fam_of, last_case):
    rows = feats[feats.week == week].set_index("district_id")
    by_family = {}
    for did in rows.index:
        by_family.setdefault(fam_of[did], []).append(did)
    dengue = {}
    for fam, ids in by_family.items():
        b = bundles[(model_id, fam)]
        X = rows.loc[ids, FEATURES[fam]].values.astype(float)
        assert not np.isnan(X).any(), f"variables incompletas para la familia {fam}"
        prob = b["clf"].predict_proba(X)[:, 1]
        q = predict_cases(b["regs"], X)
        for i, did in enumerate(ids):
            dengue[did] = (float(prob[i]), float(q["p10"][i]), float(q["p50"][i]), float(q["p90"][i]), b["base_rate"], fam)

    out = []
    for did, row in rows.iterrows():
        prob, p10, p50, p90, base_rate, fam = dengue[did]
        values = {f: num(row[f]) for f in DENGUE_FEATURES + ["tmean_change"]}
        for disease in DISEASES:
            values[f"{disease}_inc_0_3"] = None if pd.isna(row[f"{disease}_inc_0_3"]) else num(np.log1p(row[f"{disease}_inc_0_3"]))
        values = {k: v for k, v in values.items() if v is not None}
        conf_label, conf_score = confidence(p10, p50, p90, prob, fam)
        risks = {"dengue": {"prob": round(prob, 3), "casos_p10": round(p10), "casos_p50": round(p50), "casos_p90": round(p90),
                            "confianza": conf_label, "confianza_score": conf_score}}
        models = simple_models[fam]
        for disease, model in models.items():
            feat_row = {**values, "own_inc_0_3": values.get(f"{disease}_inc_0_3")}
            if all(feat_row.get(f) is not None for f in model["features"]):
                risks[disease] = {"prob": round(simple_proba(model, feat_row), 3)}
        for r in risks.values():
            r["nivel"] = level_of(r["prob"])
        base_rates = {"dengue": base_rate, **{k: m["base_rate"] for k, m in models.items() if k in risks}}
        top = rank_risks(risks, base_rates)
        entry = {
            "district_id": did,
            "modelo_tipo": fam,
            "ultimo_dato_casos": str(last_case.date()),
            "features": values,
            "riesgos": risks,
            "nivel": risks[top[0]]["nivel"],
            "top_riesgos": top[:3],
            "recursos": {"pruebas": math.ceil(p90 * 1.5), "camas": math.ceil(p90 * 0.04)},
            "clima": {"lluvia_ultimas_2sem": num(row.rain_0_1, 1), "lluvia_2_a_6sem": num(row.rain_2_6, 1),
                      "tmax": num(row.tmax_0, 1), "tmedia": num(row.tmean_0_3, 1)},
        }
        if model_id == "eval" and pd.notna(row.dengue_next):  # replay: lo que realmente pasó en las 4 semanas siguientes
            entry["real"] = {"casos_4_semanas": int(row.dengue_next), "brote": bool(row.dengue_outbreak)}
        out.append(entry)
    return out, {fam: {k: m["base_rate"] for k, m in simple_models[fam].items()} | {"dengue": bundles[(model_id, fam)]["base_rate"]} for fam in simple_models}


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


def _list(series, nd=None):
    """Lista JSON con null donde el dato es desconocido (nunca se rellena con ceros)."""
    return [None if pd.isna(v) else (int(v) if nd is None else round(float(v), nd)) for v in series.tolist()]


def export_series(feats, districts):
    """Serie semanal por distrito: casos reales (null = sin dato), umbral de brote, lluvia y temperatura."""
    weeks = sorted(feats.week.unique())
    out = {"semanas": [pd.Timestamp(w).strftime("%Y-%m-%d") for w in weeks], "distritos": {}}
    for district_id, d in feats.groupby("district_id"):
        d = d.set_index("week").reindex(weeks)
        pop = districts.loc[district_id, "population"]
        out["distritos"][district_id] = {
            "dengue": _list(d.dengue),
            "inc": _list(d.dengue / pop * 1e5, 1),
            "canal": _list((d.canal_now * pop / 1e5).fillna(0), 1),
            "lluvia": _list(d.rain_mm.fillna(0), 1),
            "tmax": _list(d.tmax.fillna(0), 1),
            # Piura: casos de 2025–2026 del Gobierno Regional (contexto; no entra al entrenamiento)
            "gore": _list(d.dengue_gore) if d.dengue_gore.notna().any() else None,
        }
    return out


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main():
    feats = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    bundles = load_bundles()
    coverage = read_json(DATA_PROCESSED / "coverage.json")
    last_case = pd.Timestamp(coverage["dengue"]["hasta"])
    daily = hazards.load_daily()
    flood_th = hazards.thresholds(daily)
    forecast = hazards.load_forecast()
    simple_models = json.loads((MODELS / "simple_models.json").read_text(encoding="utf-8"))
    metrics = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))
    districts = districts_frame().set_index("district_id")
    enso = pd.read_parquet(DATA_PROCESSED / "enso_weekly.parquet").set_index("week")

    now_week = feats.dropna(subset=CLIMATE_FEATURES).week.max()
    snapshots_def = [
        ("actual", "Hoy", now_week, "prod"),
        ("2023", "Verano 2023 (Ciclón Yaku + Niño costero)", epidemic_weeks(feats, 2023), "eval"),
        ("2017", "Verano 2017 (Niño costero)", epidemic_weeks(feats, 2017), "eval"),
    ]
    snapshots = {}
    for key, label, week, model_id in snapshots_def:
        is_now = key == "actual"
        rows = feats[feats.week == week].set_index("district_id")
        if is_now:
            # Modelo "con casos" solo si hay casos recientes Y las variables están completas; si no, solo clima
            fresh = (week - last_case).days <= FRESH_DAYS
            fam_of = {did: ("casos" if fresh and rows.loc[did, FEATURES["casos"]].notna().all() else "clima") for did in rows.index}
        else:
            fam_of = {did: "casos" for did in rows.index}
        preds, tasa_base = predict_snapshot(feats, week, model_id, bundles, simple_models, fam_of, last_case)
        # Lluvias extremas: hoy = últimos 14 días observados + 16 de pronóstico; replay = solo lo observado hasta esa semana
        obs_end = daily.time.max() if is_now else week + pd.Timedelta(days=6)
        flood, flood_series = hazards.snapshot(daily, forecast, flood_th, obs_end, use_forecast=is_now)
        for p in preds:
            p["inundacion"] = flood[p["district_id"]]
        primary = bundles[(model_id, "clima" if is_now else "casos")]
        snapshots[key] = {
            "etiqueta": label,
            "semana": week.strftime("%Y-%m-%d"),
            "nino12": round(float(enso.loc[week, "nino12_anom"]), 2),
            "oni": round(float(enso.loc[week, "oni"]), 2),
            "modelo": {"id": model_id, "origen": primary.get("origen", "campeón de evaluación"),
                       "entrenado_hasta": primary.get("entrenado_hasta", "2021-12-27"),
                       "familia": "clima" if is_now else "casos",
                       "distritos_con_casos_recientes": sum(1 for v in fam_of.values() if v == "casos")},
            "ventana_lluvia": {"hasta": obs_end.strftime("%Y-%m-%d"), "con_pronostico": is_now and forecast is not None},
            "tasa_base": tasa_base,
            "distritos": preds,
            "inundacion_serie": flood_series,
        }
        n_high = sum(p["riesgos"]["dengue"]["nivel"] == "alto" for p in preds)
        types = pd.Series([p["modelo_tipo"] for p in preds]).value_counts().to_dict()
        print(f"  {key}: semana {week.date()} — modelos {types} — {n_high} distritos en riesgo alto de dengue")

    app = {
        "generado": pd.Timestamp.now(tz="America/Lima").strftime("%Y-%m-%d %H:%M"),
        "horizonte_semanas": HORIZON_WEEKS,
        "distritos": districts.reset_index().to_dict(orient="records"),
        "escenarios": snapshots,
        "referencia_2023": scenario_reference(feats),
        "pronostico": forecast_summary(),
        "modelo": {
            "features": FEATURES,
            "dengue_features": DENGUE_FEATURES,
            "rain_features": RAIN_FEATURES,
            "temp_features": TEMP_FEATURES,
            "simple_features": SIMPLE_FEATURES,
            "simples": {variant: {k: {kk: vv for kk, vv in v.items() if kk != "threshold_by_district"} for k, v in models.items()}
                        for variant, models in simple_models.items()},
            "umbrales_nivel": LEVEL_THRESHOLDS,
        },
        "datos": {
            "cobertura": coverage,
            "licencia": "Open Data Commons Attribution License (ODC-By)",
            "cita": "CDC-MINSA (Centro Nacional de Epidemiología), Plataforma Nacional de Datos Abiertos; Gobierno Regional de Piura; Open-Meteo; NOAA CPC.",
            "ultimo_caso_oficial": str(last_case.date()),
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
    payload = json.dumps(app, ensure_ascii=False, separators=(",", ":"), allow_nan=False)  # NaN sería JSON inválido
    (WEB_DATA / "app.json").write_text(payload, encoding="utf-8")
    series = json.dumps(export_series(feats, districts), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    (WEB_DATA / "series.json").write_text(series, encoding="utf-8")
    print(f"Exportado series.json ({len(series) / 1024:.0f} KB)")
    web_models = WEB_DATA.parent / "models"
    web_models.mkdir(exist_ok=True)
    for f in web_models.glob("*.onnx"):
        f.unlink()  # evita modelos viejos que ya no existen
    for f in MODELS.glob("*.onnx"):
        shutil.copy(f, web_models / f.name)

    API_MODELS.mkdir(parents=True, exist_ok=True)
    for f in API_MODELS.glob("*.joblib"):
        f.unlink()
    for f in MODELS.glob("dengue*.joblib"):
        shutil.copy(f, API_MODELS / f.name)
    (API_MODELS / "app.json").write_text(payload, encoding="utf-8")
    print(f"Exportado app.json ({len(payload) / 1024:.0f} KB), {len(list(MODELS.glob('*.onnx')))} modelos ONNX y {len(list(MODELS.glob('dengue*.joblib')))} modelos joblib")


if __name__ == "__main__":
    main()
