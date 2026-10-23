"""Lógica de predicción compartida por los endpoints (misma que usa la web en el navegador)."""
import json
import math
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np

MODELS_DIR = Path(__file__).parent / "models"
ORDER = {"alto": 2, "medio": 1, "bajo": 0}
FILES = {("eval", "casos"): "dengue.joblib", ("eval", "clima"): "dengue_clima.joblib",
         ("prod", "casos"): "dengue_prod.joblib", ("prod", "clima"): "dengue_clima_prod.joblib"}


@lru_cache
def load():
    """app.json + modelos. 'eval' = campeón entrenado con 2015–2021; 'prod' = el que ganó el reentrenamiento.
    Familia 'casos' = usa casos recientes; 'clima' = solo clima (la que predice hoy si no hay casos al día)."""
    app = json.loads((MODELS_DIR / "app.json").read_text(encoding="utf-8"))
    bundles = {}
    for key, name in FILES.items():
        path = MODELS_DIR / name
        bundles[key] = joblib.load(path if path.exists() else MODELS_DIR / FILES[("eval", key[1])])
    return app, bundles


def level_of(prob, thresholds):
    if prob >= thresholds["alto"]:
        return "alto"
    if prob >= thresholds["medio"]:
        return "medio"
    return "bajo"


def confidence(p10, p50, p90, prob, family):
    """Sin casos recientes ('clima') la confianza nunca pasa de media: el modelo ordena bien los distritos
    pero calcula mal cuántos casos habrá."""
    spread = (p90 - p10) / (p50 + 10)
    score = 0.6 * abs(prob - 0.5) * 2 + 0.4 * max(0.0, 1 - spread / 3)
    label = "alta" if score >= 0.6 else "media" if score >= 0.35 else "baja"
    if family == "clima":
        label = "baja" if label == "baja" else "media"
        score = min(score, 0.5)
    return label, round(score, 2)


def apply_scenario(features, reference, rain_pct, temp_delta, model_meta):
    """lluvia_pct: 0 = clima observado, 100 = lluvias como el pico de 2023 en ese distrito."""
    f = dict(features)
    k = rain_pct / 100
    for name in model_meta["rain_features"]:
        f[name] = max(0.0, f[name] + k * (reference[name] - features[name]))
    for name in model_meta["temp_features"]:
        f[name] = f[name] + temp_delta
    return f


def predict_district(district_id, escenario="actual", lluvia_pct=0.0, temp_delta=0.0):
    app, bundles = load()
    snap = app["escenarios"][escenario]
    base = next((d for d in snap["distritos"] if d["district_id"] == district_id), None)
    if base is None:
        raise KeyError(district_id)
    family = base["modelo_tipo"]
    bundle = bundles[(snap["modelo"]["id"], family)]
    meta = app["modelo"]
    f = apply_scenario(base["features"], app["referencia_2023"][district_id], lluvia_pct, temp_delta, meta)

    X = np.array([[f[name] for name in meta["features"][family]]], dtype=float)
    prob = float(bundle["clf"].predict_proba(X)[0, 1])
    q = {k: float(np.expm1(r.predict(X)[0]).clip(min=0)) for k, r in bundle["regs"].items()}
    q = dict(zip(("p10", "p50", "p90"), sorted((q["p10"], q["p50"], q["p90"]))))
    conf_label, conf_score = confidence(q["p10"], q["p50"], q["p90"], prob, family)
    thresholds = meta["umbrales_nivel"]
    riesgos = {"dengue": {"prob": round(prob, 3), "nivel": level_of(prob, thresholds),
                          "casos_p10": round(q["p10"]), "casos_p50": round(q["p50"]),
                          "casos_p90": round(q["p90"]), "confianza": conf_label,
                          "confianza_score": conf_score}}
    for disease, m in meta["simples"][family].items():
        values = {name: (f.get(f"{disease}_inc_0_3") if name == "own_inc_0_3" else f.get(name)) for name in m["features"]}
        if any(v is None for v in values.values()):
            continue
        z = m["intercept"] + sum(c * (values[name] - mu) / sd for name, mu, sd, c in zip(m["features"], m["mean"], m["scale"], m["coef"]))
        p = 1 / (1 + math.exp(-z))
        riesgos[disease] = {"prob": round(p, 3), "nivel": level_of(p, thresholds)}

    rates = snap["tasa_base"][family]
    top = sorted(riesgos, key=lambda k: (-ORDER[riesgos[k]["nivel"]], -riesgos[k]["prob"] / rates[k]))
    acciones = [a.format(tests=math.ceil(q["p90"] * 1.5), beds=math.ceil(q["p90"] * 0.04))
                for a in app["contenido"]["autoridad"]["dengue"][riesgos["dengue"]["nivel"]]]
    flood = base["inundacion"]
    return {
        "district_id": district_id,
        "escenario": escenario,
        "semana_base": snap["semana"],
        "horizonte_semanas": app["horizonte_semanas"],
        "modelo": snap["modelo"],
        "modelo_tipo": family,
        "ultimo_dato_casos": base["ultimo_dato_casos"],
        "aviso": ("Estimación solo con clima: el último caso oficial es del " + base["ultimo_dato_casos"] +
                  ". Sirve para priorizar qué distritos vigilar, no para calcular cuántos casos habrá.") if family == "clima" else None,
        "riesgos": riesgos,
        "nivel": riesgos[top[0]]["nivel"],
        "top_riesgos": top[:3],
        "lluvias_extremas": flood,
        "acciones_autoridad_dengue": acciones,
        "acciones_autoridad_lluvias": app["contenido"]["lluvia_extrema"]["autoridad"][flood["nivel"]],
        "acciones_ciudadano": {d: app["contenido"]["ciudadano"][d] for d in top[:3]},
    }


def plan_inputs(escenario="actual", departamento=None):
    """Distritos del escenario en el formato que espera optimizer.optimize()."""
    app, _ = load()
    by_id = {d["district_id"]: d for d in app["distritos"]}
    rows = []
    for p in app["escenarios"][escenario]["distritos"]:
        d = by_id[p["district_id"]]
        if departamento and d["department"] != departamento:
            continue
        r = p["riesgos"]["dengue"]
        rows.append({"district_id": d["district_id"], "distrito": d["district"], "poblacion": d["population"],
                     "prob": r["prob"], "casos_p10": r["casos_p10"], "casos_p50": r["casos_p50"], "casos_p90": r["casos_p90"]})
    return rows
