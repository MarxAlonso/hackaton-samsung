"""Paso 5 — Monitoreo del modelo en producción (deriva y desempeño).

Responde dos preguntas cada semana:
  1. ¿Los datos de entrada de hoy se parecen a los de entrenamiento? (data drift)
     PSI por variable, comparando la misma época del año (para no confundir estación con deriva)
     y % de valores fuera del rango visto al entrenar.
  2. ¿El modelo sigue acertando? (model drift)
     AUC, Brier y calibración por trimestre sobre semanas cuyo resultado ya se conoce.

Reglas de decisión (umbrales estándar de la industria):
  PSI < 0,10 estable · 0,10–0,25 vigilar · > 0,25 deriva fuerte.

Salida: reports/monitoring.json (lo muestra la página "Cómo funciona" y decide si hay que reentrenar).
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from config import DATA_PROCESSED, MODELS, REPORTS, TRAIN_END
from features import DENGUE_FEATURES, complete_rows

RECENT_WEEKS = 26
EPS = 1e-4
FRIENDLY = {
    "rain_0_1": "Lluvia últimas 2 semanas", "rain_2_6": "Lluvia hace 2–6 semanas", "rain_7_12": "Lluvia hace 7–12 semanas",
    "tmean_0_3": "Temperatura media", "tmax_0": "Temperatura máxima", "humidity_0_3": "Humedad",
    "nino12": "Mar Niño 1+2", "oni": "Índice ONI", "inc_0": "Incidencia de la semana",
    "inc_0_3": "Incidencia 4 semanas", "inc_52": "Incidencia del año", "canal_next": "Umbral de brote",
    "altitude": "Altitud", "water_access": "Agua por red", "log_pop": "Población", "week_sin": "Época (ciclo)", "week_cos": "Época (fase)",
}


def psi(train, recent, bins=10):
    """Population Stability Index con cortes por deciles del entrenamiento y colas abiertas."""
    train, recent = np.asarray(train, float), np.asarray(recent, float)
    edges = np.unique(np.quantile(train, np.linspace(0, 1, bins + 1)[1:-1]))
    if len(edges) < 2:  # variable casi constante (p. ej. altitud): usa corte por igualdad
        edges = np.unique(np.concatenate([edges, [np.median(train) + 1e-9]]))
    cut = np.concatenate([[-np.inf], edges, [np.inf]])
    p = np.histogram(train, cut)[0] / len(train)
    q = np.histogram(recent, cut)[0] / len(recent)
    p, q = np.clip(p, EPS, None), np.clip(q, EPS, None)
    return float(np.sum((q - p) * np.log(q / p)))


def status_of(value, warn=0.10, alert=0.25):
    return "alerta" if value > alert else "vigilar" if value > warn else "estable"


def feature_drift(feats):
    last = feats.week.max()
    recent = feats[feats.week > last - pd.Timedelta(weeks=RECENT_WEEKS)].dropna(subset=DENGUE_FEATURES)
    train_all = feats[feats.week <= TRAIN_END].dropna(subset=DENGUE_FEATURES)
    # misma época del año que la ventana reciente
    wk = set(recent.week.dt.isocalendar().week.astype(int))
    train = train_all[train_all.week.dt.isocalendar().week.astype(int).isin(wk)]
    rows = []
    for f in DENGUE_FEATURES:
        if f in ("week_sin", "week_cos", "altitude", "log_pop", "water_access"):
            continue  # estáticas o de calendario: no pueden derivar
        v = psi(train[f], recent[f])
        lo, hi = train_all[f].min(), train_all[f].max()
        out = float(((recent[f] > hi) | (recent[f] < lo)).mean())
        rows.append({"variable": f, "nombre": FRIENDLY.get(f, f), "psi": round(v, 3), "estado": status_of(v),
                     "fuera_de_rango_pct": round(out * 100, 1),
                     "entrenamiento_max": round(float(hi), 2), "reciente_max": round(float(recent[f].max()), 2)})
    rows.sort(key=lambda r: -r["psi"])
    return rows, {"desde": str(recent.week.min().date()), "hasta": str(recent.week.max().date()), "filas": int(len(recent))}


def performance_by_quarter(feats):
    bundle = joblib.load(MODELS / "dengue.joblib")
    data = complete_rows(feats)
    data = data[data.week > TRAIN_END].copy()
    data["p"] = bundle["clf"].predict_proba(data[DENGUE_FEATURES].values)[:, 1]
    data["q"] = data.week.dt.to_period("Q").astype(str)
    rows = []
    for q, g in data.groupby("q"):
        y = g.dengue_outbreak.values
        row = {"periodo": q, "n": int(len(g)), "tasa_brote": round(float(y.mean()), 3),
               "brier": round(float(brier_score_loss(y, g.p)), 4),
               "prob_media": round(float(g.p.mean()), 3)}
        row["auc"] = round(float(roc_auc_score(y, g.p)), 3) if 0 < y.sum() < len(y) else None
        rows.append(row)
    return rows, data


def main():
    REPORTS.mkdir(exist_ok=True)
    feats = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    drift, window = feature_drift(feats)
    quarters, data = performance_by_quarter(feats)
    metrics = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))
    brier_ref = metrics["dengue"]["modelo"]["brier"]

    recent_q = [q for q in quarters if q["n"] >= 200][-2:]
    recent_brier = float(np.mean([q["brier"] for q in recent_q])) if recent_q else brier_ref
    gap = max((abs(q["prob_media"] - q["tasa_brote"]) for q in recent_q), default=0.0)

    importance = list(metrics["dengue"]["importancia_variables"])[:6]
    key_alerts = [d for d in drift if d["estado"] == "alerta" and d["variable"] in importance]
    ood = [d for d in drift if d["fuera_de_rango_pct"] >= 20]
    reasons = []
    if key_alerts:
        reasons.append("deriva fuerte (PSI > 0,25) en variables clave: " + ", ".join(d["nombre"] for d in key_alerts))
    if ood:
        reasons.append("valores fuera del rango de entrenamiento en: " + ", ".join(d["nombre"] for d in ood))
    if recent_brier > 1.5 * brier_ref:
        reasons.append(f"el error de probabilidad reciente (Brier {recent_brier:.3f}) supera 1,5× el de validación ({brier_ref:.3f})")
    if gap > 0.10:
        reasons.append("las probabilidades están descalibradas en el último trimestre")

    report = {
        "generado": pd.Timestamp.now(tz="America/Lima").strftime("%Y-%m-%d %H:%M"),
        "ventana_reciente": window,
        "deriva_variables": drift,
        "desempeno_por_trimestre": quarters,
        "brier_validacion": brier_ref,
        "brier_reciente": round(recent_brier, 4),
        "estado": "reentrenar" if (key_alerts or recent_brier > 1.5 * brier_ref or gap > 0.10) else ("vigilar" if ood else "estable"),
        "motivos": reasons,
        "reglas": "PSI < 0,10 estable · 0,10–0,25 vigilar · > 0,25 deriva fuerte; reentrenar si hay deriva fuerte en variables clave, Brier > 1,5× o calibración fuera de ±10 puntos.",
    }
    (REPORTS / "monitoring.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Monitoreo — ventana {window['desde']} → {window['hasta']} ({window['filas']} filas)")
    for d in drift[:6]:
        print(f"  {d['nombre']:28s} PSI {d['psi']:6.3f}  {d['estado']:8s} fuera de rango {d['fuera_de_rango_pct']:5.1f}%")
    print("Brier por trimestre:", [(q["periodo"], q["brier"]) for q in quarters][-6:])
    print(f"Estado: {report['estado'].upper()}")
    for r in reasons:
        print("  -", r)


if __name__ == "__main__":
    main()
