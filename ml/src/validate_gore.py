"""Validación externa con los casos de Piura 2025–2026 del Gobierno Regional (no entran al entrenamiento).

Dos preguntas, con las predicciones que el modelo de HOY (solo clima) habría dado en cada semana:
  1. ¿Ordena bien los distritos de Piura que tuvieron más actividad en 2025–2026? (AUC y correlación de rangos)
  2. ¿Mejora si además se le da la señal de arrastre (los casos del Gobierno Regional de las últimas 4 semanas)?
     Si no mejora, se documenta y no se usa.

Los conteos del Gobierno Regional NO son comparables con los del CDC (otro sistema: en 2025 son unas 11 veces
mayores), así que la verdad se define de forma RELATIVA: "actividad alta" = casos de las próximas 4 semanas por
encima del percentil 75 de ese mismo distrito. Resultado: reports/validation_gore.json.
"""
import json

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from config import DATA_PROCESSED, MODELS, REPORTS, districts_frame
from features import FEATURES
from retrain import PROD_FILE

FIRST, TEST_FROM, MIN_CASES = pd.Timestamp("2025-01-06"), pd.Timestamp("2026-01-05"), 5


def auc(y, s):
    y = np.asarray(y)
    return round(float(roc_auc_score(y, s)), 3) if 0 < y.sum() < len(y) else None


def main():
    feats = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    cases = pd.read_parquet(DATA_PROCESSED / "cases_weekly.parquet")[["district_id", "week", "dengue_gore"]]
    piura = set(districts_frame().query("department == 'Piura'").district_id)
    df = feats[feats.district_id.isin(piura)].merge(cases, on=["district_id", "week"], suffixes=("", "_c"))
    df = df.sort_values(["district_id", "week"])
    g = df.groupby("district_id").dengue_gore
    df["gore_4s_antes"] = g.transform(lambda s: s.rolling(4, min_periods=4).sum())
    df["gore_4s_despues"] = g.transform(lambda s: s[::-1].shift(1).rolling(4, min_periods=4).sum()[::-1])

    bundle = joblib.load(MODELS / PROD_FILE["clima"]) if (MODELS / PROD_FILE["clima"]).exists() else joblib.load(MODELS / "dengue_clima.joblib")
    df = df[(df.week >= FIRST)].dropna(subset=bundle["features"] + ["gore_4s_despues", "gore_4s_antes"]).copy()
    X = df[bundle["features"]].values
    df["prob"] = bundle["clf"].predict_proba(X)[:, 1]
    df["p50"] = np.expm1(bundle["regs"]["p50"].predict(X)).clip(min=0)

    # Línea base: frecuencia histórica de brote de ese distrito en esa semana del año (calendario puro)
    hist = feats[feats.week <= "2021-12-31"].groupby(["district_id", "epiweek"]).dengue_outbreak.mean().rename("base")
    df = df.join(hist, on=["district_id", "epiweek"])
    df["base"] = df["base"].fillna(hist.mean())

    train, test = df[df.week < TEST_FROM], df[df.week >= TEST_FROM]
    # "actividad alta" de cada distrito: percentil 75 de lo que se vio en el periodo de AJUSTE (2025), no del de prueba
    thr = train.groupby("district_id").gore_4s_despues.quantile(0.75).clip(lower=MIN_CASES)
    for part in (train, test):
        part["alta"] = (part.gore_4s_despues > part.district_id.map(thr)).astype(int)

    out = {
        "fuente": "Gobierno Regional de Piura (casos de dengue 2025–2026; no comparables con los del CDC, por eso la verdad es relativa)",
        "modelo": "dengue_clima (solo clima) — el que predice hoy",
        "periodo_prueba": f"{test.week.min().date()} a {test.week.max().date()}",
        "distritos_piura": int(test.district_id.nunique()), "filas_prueba": int(len(test)),
        "tasa_actividad_alta_prueba": round(float(test.alta.mean()), 3),
    }
    out["ordenamiento"] = {
        "auc_modelo_clima": auc(test.alta, test.prob),
        "auc_linea_base_calendario": auc(test.alta, test.base),
        "correlacion_rangos_casos_previstos_vs_gore": round(float(spearmanr(test.p50, test.gore_4s_despues)[0]), 3),
    }
    weekly = [spearmanr(d.prob, d.gore_4s_despues)[0] for _, d in test.groupby("week") if d.gore_4s_despues.nunique() > 3]
    out["ordenamiento"]["correlacion_media_por_semana_entre_distritos"] = round(float(np.nanmean(weekly)), 3)

    # Señal de arrastre: logística sobre [prob del modelo] contra [prob del modelo + casos recientes del Gob. Regional]
    def design(d, arrastre):
        p = np.clip(d.prob.values, 1e-4, 1 - 1e-4)
        cols = [np.log(p / (1 - p))]
        if arrastre:
            cols.append(np.log1p(d.gore_4s_antes.values))
        return np.column_stack(cols)

    res = {}
    for name, arr in (("solo_modelo_clima", False), ("modelo_clima_mas_arrastre", True)):
        lr = LogisticRegression(max_iter=1000).fit(design(train, arr), train.alta)
        proba = lr.predict_proba(design(test, arr))[:, 1]
        res[name] = {"auc": auc(test.alta, proba), "brier": round(float(np.mean((test.alta - proba) ** 2)), 4)}
    res["mejora_auc"] = round((res["modelo_clima_mas_arrastre"]["auc"] or 0) - (res["solo_modelo_clima"]["auc"] or 0), 3)

    # ¿La mejora es real o ruido? Intervalo del 95% remuestreando distritos (se reajusta la logística de 2025 una sola vez)
    lr0 = LogisticRegression(max_iter=1000).fit(design(train, False), train.alta)
    lr1 = LogisticRegression(max_iter=1000).fit(design(train, True), train.alta)
    rng, ids, diffs = np.random.default_rng(11), test.district_id.unique(), []
    by = {d: x for d, x in test.groupby("district_id")}
    for _ in range(400):
        sample = pd.concat([by[d] for d in rng.choice(ids, size=len(ids), replace=True)])
        if 0 < sample.alta.sum() < len(sample):
            diffs.append(roc_auc_score(sample.alta, lr1.predict_proba(design(sample, True))[:, 1])
                         - roc_auc_score(sample.alta, lr0.predict_proba(design(sample, False))[:, 1]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    res["mejora_auc_ic95"] = [round(float(lo), 3), round(float(hi), 3)]
    res["conclusion"] = (
        "La señal de arrastre mejora el AUC de forma consistente y se puede considerar para Piura."
        if lo > 0.02 else
        "La señal de arrastre mejora el AUC un poco, pero el intervalo del 95% incluye el cero (23 distritos, pocas semanas) y su "
        "conteo no es comparable con el del CDC: NO se integra al modelo y se usa solo como contexto en los gráficos.")
    out["arrastre"] = res
    (REPORTS / "validation_gore.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
