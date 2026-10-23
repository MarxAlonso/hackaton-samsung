"""Paso 4 — Entrenamiento y evaluación con casos REALES del CDC-MINSA.

Dengue (dos familias de modelo, cada una con clasificador de brote + 3 regresores de casos):
  - "casos": usa clima, El Niño, calendario Y casos recientes. Es el más preciso, pero necesita datos al día.
  - "clima": solo clima, El Niño y calendario. Predice HOY cuando el último caso oficial es antiguo.
  Brote = alguna de las próximas 4 semanas supera el canal endémico (percentil 75 histórico) con ≥ 5 casos.
  Cuantiles de casos: pesimista (P90), probable (P50), optimista (P10).
Otras enfermedades (leptospirosis, EDA, IRA reales; golpe de calor simulado): regresión logística de
"semanas de riesgo alto" (casos de las próximas 4 semanas sobre el percentil 80 histórico del distrito),
también con y sin casos recientes.

Validación temporal: entrena con 2015–2021 y evalúa con 2022 en adelante (con datos reales: incluye las
epidemias de 2023 y 2024, que el modelo nunca vio). El último año del archivo nacional es provisional y no se usa.
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score,
                             mean_absolute_error, precision_score, recall_score, roc_auc_score)
from sklearn.preprocessing import StandardScaler

from config import DATA_PROCESSED, DISEASES, MODELS, REPORTS, SEED, TRAIN_END
from features import FEATURES, SIMPLE_FEATURES, build, complete_rows

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}
PARAMS = {"n_estimators_clf": 250, "n_estimators_reg": 300, "max_depth": 3, "lr_clf": 0.05, "lr_reg": 0.08, "subsample": 0.8}
# Prefijo de los archivos de cada familia: "" = con casos, "clima_" = solo clima (y "prod_" delante para producción)
FAMILY_PREFIX = {"casos": "", "clima": "clima_"}
FAMILY_FILE = {"casos": "dengue.joblib", "clima": "dengue_clima.joblib"}


def classification_metrics(y, proba, threshold=0.5):
    y = np.asarray(y).astype(int)
    pred = (proba >= threshold).astype(int)
    both = 0 < y.sum() < len(y)
    return {
        "auc": round(float(roc_auc_score(y, proba)), 3) if both else None,
        "pr_auc": round(float(average_precision_score(y, proba)), 3) if both else None,
        "brier": round(float(brier_score_loss(y, proba)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 3),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 3),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 3),
    }


def reliability(y, proba, bins=10):
    """¿Cuando el modelo dice 70%, ocurre ~70% de las veces?"""
    y = np.asarray(y)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(proba, edges) - 1, 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = idx == b
        if mask.sum() >= 20:
            rows.append({"predicho": round(float(proba[mask].mean()), 3),
                         "observado": round(float(y[mask].mean()), 3), "n": int(mask.sum())})
    return rows


def fit_dengue_models(train, features):
    """Ajusta el clasificador de brote y los 3 regresores de casos (P10/P50/P90)."""
    X_tr = train[features].values
    clf = GradientBoostingClassifier(n_estimators=PARAMS["n_estimators_clf"], max_depth=PARAMS["max_depth"],
                                     learning_rate=PARAMS["lr_clf"], subsample=PARAMS["subsample"], random_state=SEED)
    clf.fit(X_tr, train.dengue_outbreak.values.astype(int))
    regs = {}
    log_tr = np.log1p(train.dengue_next.values)
    for name, alpha in QUANTILES.items():
        # P50 con error cuadrático en escala log (≈ mediana, estable con muchas semanas en 0);
        # P10/P90 con pérdida cuantílica. El orden P10 ≤ P50 ≤ P90 se fuerza al predecir.
        loss = {"loss": "squared_error"} if name == "p50" else {"loss": "quantile", "alpha": alpha}
        reg = GradientBoostingRegressor(**loss, n_estimators=PARAMS["n_estimators_reg"], max_depth=PARAMS["max_depth"],
                                        learning_rate=PARAMS["lr_reg"], subsample=PARAMS["subsample"], random_state=SEED)
        reg.fit(X_tr, log_tr)
        regs[name] = reg
    return clf, regs


def predict_cases(regs, X):
    """P10/P50/P90 ordenados (nunca cruzados) en casos."""
    preds = {k: np.expm1(r.predict(X)).clip(min=0) for k, r in regs.items()}
    stacked = np.sort(np.vstack([preds["p10"], preds["p50"], preds["p90"]]), axis=0)
    return dict(zip(("p10", "p50", "p90"), stacked))


def baseline_proba(family, train, test):
    """Línea base de cada familia.
    casos: el criterio actual del MINSA (si esta semana ya está sobre el canal endémico, hay brote).
    clima: la frecuencia histórica de brote de ese distrito en esa semana del año (calendario puro)."""
    if family == "casos":
        return ((test.inc_0 > test.canal_now) & (test.dengue >= 5)).astype(float).values
    hist = train.groupby(["district_id", "epiweek"]).dengue_outbreak.mean().rename("p")
    p = test.join(hist, on=["district_id", "epiweek"])["p"]
    return p.fillna(train.dengue_outbreak.mean()).values


def train_dengue(train, test, features, family):
    X_te = test[features].values
    y_te = test.dengue_outbreak.values.astype(int)
    clf, regs = fit_dengue_models(train, features)
    proba = clf.predict_proba(X_te)[:, 1]
    base = baseline_proba(family, train, test)
    metrics = {
        "modelo": classification_metrics(y_te, proba),
        "linea_base": classification_metrics(y_te, base),
        "linea_base_nombre": "canal endémico (criterio del MINSA)" if family == "casos" else "frecuencia histórica de la semana del año",
        "confiabilidad": reliability(y_te, proba),
        "tasa_brote_test": round(float(y_te.mean()), 3),
        "filas_entrenamiento": int(len(train)), "filas_prueba": int(len(test)),
    }
    # Subconjuntos difíciles: el AUC global se infla con semanas secas o distritos de altura
    season = test.week.dt.month.between(1, 6).values
    onset = (test.inc_0 <= test.canal_now).values  # todavía no hay brote: ¿lo anticipa?
    metrics["subconjuntos"] = {
        "temporada_lluvias": {"auc": classification_metrics(y_te[season], proba[season])["auc"],
                              "tasa_brote": round(float(y_te[season].mean()), 3), "n": int(season.sum())},
        "anticipacion_brote_nuevo": {**{k: classification_metrics(y_te[onset], proba[onset])[k] for k in ("auc", "pr_auc")},
                                     "tasa_brote": round(float(y_te[onset].mean()), 3), "n": int(onset.sum())},
    }
    preds = predict_cases(regs, X_te)
    y_cases = test.dengue_next.values
    naive = test.groupby("district_id").dengue.transform(lambda s: s.rolling(4, min_periods=1).sum()).values
    metrics["casos"] = {
        "mae_modelo_p50": round(float(mean_absolute_error(y_cases, preds["p50"])), 2),
        "mae_linea_base_ultimas_4_semanas": round(float(mean_absolute_error(y_cases, naive)), 2),
        "cobertura_p10_p90": round(float(((y_cases >= preds["p10"]) & (y_cases <= preds["p90"])).mean()), 3),
    }
    metrics["importancia_variables"] = dict(sorted(
        ((f, round(float(v), 4)) for f, v in zip(features, clf.feature_importances_)), key=lambda kv: -kv[1]))
    return clf, regs, metrics


def walk_forward(data, features, years=(2022, 2023, 2024)):
    """Evaluación progresiva: para cada año, se entrena con TODO lo anterior y se prueba en ese año.
    Muestra cuánto mejora el modelo cuando ya vio epidemias, y se compara con "no tener información"
    (predecir siempre la tasa de brote del entrenamiento)."""
    rows = []
    for y in years:
        tr = data[data.week < f"{y}-01-01"]
        te = data[(data.week >= f"{y}-01-01") & (data.week < f"{y + 1}-01-01")]
        if te.empty or tr.dengue_outbreak.nunique() < 2:
            continue
        clf, regs = fit_dengue_models(tr, features)
        X, yte = te[features].values, te.dengue_outbreak.values.astype(int)
        proba = clf.predict_proba(X)[:, 1]
        cases = predict_cases(regs, X)
        base = float(tr.dengue_outbreak.mean())
        m = classification_metrics(yte, proba)
        rows.append({
            "anio": y, "entrenamiento_hasta": str(tr.week.max().date()), "filas_prueba": int(len(te)),
            "tasa_brote": round(float(yte.mean()), 3), "auc": m["auc"], "recall": m["recall"], "brier": m["brier"],
            "brier_sin_informacion": round(float(np.mean((yte - base) ** 2)), 4),
            "mae_casos_p50": round(float(mean_absolute_error(te.dengue_next.values, cases["p50"])), 2),
            "cobertura_p10_p90": round(float(((te.dengue_next.values >= cases["p10"]) & (te.dengue_next.values <= cases["p90"])).mean()), 3),
        })
    return rows


def train_simple(train, test):
    """Logística por enfermedad y por variante (con casos recientes / solo clima)."""
    models, metrics = {v: {} for v in SIMPLE_FEATURES}, {v: {} for v in SIMPLE_FEATURES}
    for disease in DISEASES:
        if disease == "dengue":
            continue
        tr_all = train[train[f"{disease}_next"].notna()]
        thresholds = tr_all.groupby("district_id")[f"{disease}_next"].quantile(0.8)
        for variant, cols in SIMPLE_FEATURES.items():
            def frame(df):
                df = df[df[f"{disease}_next"].notna()].assign(own_inc_0_3=lambda d: np.log1p(d[f"{disease}_inc_0_3"]))
                df = df.dropna(subset=cols)
                return df[cols].values, (df[f"{disease}_next"] > df.district_id.map(thresholds)).astype(int).values

            X_tr, y_tr = frame(train)
            X_te, y_te = frame(test)
            scaler = StandardScaler().fit(X_tr)
            lr = LogisticRegression(max_iter=2000, C=0.5).fit(scaler.transform(X_tr), y_tr)
            proba = lr.predict_proba(scaler.transform(X_te))[:, 1]
            metrics[variant][disease] = {**classification_metrics(y_te, proba), "n_prueba": int(len(y_te)), "tasa_base_prueba": round(float(y_te.mean()), 3)}
            models[variant][disease] = {
                "features": cols,
                "mean": scaler.mean_.round(6).tolist(), "scale": scaler.scale_.round(6).tolist(),
                "coef": lr.coef_[0].round(6).tolist(), "intercept": round(float(lr.intercept_[0]), 6),
                "base_rate": round(float(y_tr.mean()), 4),
                "threshold_by_district": thresholds.round(1).to_dict(),
            }
    return models, metrics


def export_onnx(clf, regs, features, prefix=""):
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    import onnxruntime as ort

    n = len(features)
    initial = [("features", FloatTensorType([None, n]))]
    onnx_clf = convert_sklearn(clf, initial_types=initial, options={id(clf): {"zipmap": False}}, target_opset=17)
    (MODELS / f"{prefix}dengue_outbreak.onnx").write_bytes(onnx_clf.SerializeToString())
    for name, reg in regs.items():
        onnx_reg = convert_sklearn(reg, initial_types=initial, target_opset=17)
        (MODELS / f"{prefix}dengue_cases_{name}.onnx").write_bytes(onnx_reg.SerializeToString())

    # Verificación: ONNX y scikit-learn deben dar lo mismo
    sample = np.random.default_rng(0).normal(size=(5, n)).astype(np.float32) * 10 + 20
    sess = ort.InferenceSession(str(MODELS / f"{prefix}dengue_outbreak.onnx"))
    onnx_proba = sess.run(None, {"features": sample})[1][:, 1]
    diff = np.abs(onnx_proba - clf.predict_proba(sample)[:, 1]).max()
    print(f"  ONNX ({prefix or 'casos'}) vs sklearn, diferencia máxima: {diff:.2e}")
    assert diff < 1e-4


def log_run(name, params, metrics, artifacts=()):
    """Registra cada entrenamiento: siempre en reports/experiments.jsonl (sirve en CI sin dependencias)
    y, si MLflow está instalado, también en ml/mlflow.db (`mlflow ui --backend-store-uri sqlite:///mlflow.db`)."""
    import datetime
    REPORTS.mkdir(exist_ok=True)
    entry = {"fecha": datetime.datetime.now().isoformat(timespec="seconds"), "run": name, "params": params, "metricas": metrics}
    with open(REPORTS / "experiments.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    try:
        import mlflow
        mlflow.set_tracking_uri(f"sqlite:///{(MODELS.parent / 'mlflow.db').as_posix()}")
        mlflow.set_experiment("alerta-salud-nino")
        with mlflow.start_run(run_name=name):
            mlflow.log_params({k: v for k, v in params.items()})
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, v)
            for a in artifacts:
                mlflow.log_artifact(str(a))
    except ImportError:
        pass
    except Exception as exc:  # el registro nunca debe detener el pipeline
        print(f"  (MLflow no pudo registrar el experimento: {type(exc).__name__}; queda en experiments.jsonl)")


def main():
    MODELS.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    feats, channel = build()
    feats.to_parquet(DATA_PROCESSED / "features.parquet", index=False)
    channel.to_parquet(DATA_PROCESSED / "endemic_channel.parquet", index=False)

    metrics = {}
    split = {}
    for family, features in FEATURES.items():
        data = complete_rows(feats, features)
        train, test = data[data.week <= TRAIN_END], data[data.week > TRAIN_END]
        split[family] = (train, test)
        print(f"[{family}] entrenamiento: {len(train):,} filas ({train.week.min().date()} a {train.week.max().date()}) | prueba: {len(test):,} filas ({test.week.min().date()} a {test.week.max().date()})")
        clf, regs, m = train_dengue(train, test, features, family)
        metrics["dengue" if family == "casos" else "dengue_clima"] = m
        m["periodo_entrenamiento"] = f"{train.week.min().date()} a {train.week.max().date()}"
        m["periodo_prueba"] = f"{test.week.min().date()} a {test.week.max().date()}"
        m["evaluacion_progresiva"] = walk_forward(data, features)
        joblib.dump({"clf": clf, "regs": regs, "features": features, "familia": family,
                     "base_rate": round(float(train.dengue_outbreak.mean()), 4)}, MODELS / FAMILY_FILE[family])
        export_onnx(clf, regs, features, FAMILY_PREFIX[family])
        mm = m["modelo"]
        log_run(f"gbm-dengue-{family}-evaluacion", {**PARAMS, "familia": family, "train_end": TRAIN_END, "features": len(features), "filas_train": int(len(train))},
                {"auc": mm["auc"], "pr_auc": mm["pr_auc"], "brier": mm["brier"], "f1": mm["f1"], "recall": mm["recall"],
                 "mae_p50": m["casos"]["mae_modelo_p50"], "cobertura_p10_p90": m["casos"]["cobertura_p10_p90"]})

    # Modelos simples de las otras 4 enfermedades: se entrenan con las filas de la familia "casos" (más exigente)
    train, test = split["casos"]
    simple_models, simple_metrics = train_simple(train, test)
    metrics["otras_enfermedades"] = simple_metrics["casos"]
    metrics["otras_enfermedades_clima"] = simple_metrics["clima"]
    metrics["periodo_entrenamiento"] = metrics["dengue"]["periodo_entrenamiento"]
    metrics["periodo_prueba"] = metrics["dengue"]["periodo_prueba"]
    metrics["datos"] = json.loads((DATA_PROCESSED / "coverage.json").read_text(encoding="utf-8"))

    (MODELS / "simple_models.json").write_text(json.dumps(simple_models, ensure_ascii=False, indent=1), encoding="utf-8")
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    for key, titulo in (("dengue", "con casos recientes"), ("dengue_clima", "solo clima (modelo de HOY)")):
        m = metrics[key]
        a, b = m["modelo"], m["linea_base"]
        print(f"\nDengue {titulo} — brote en 4 semanas (prueba {m['periodo_prueba']})")
        print(f"  Modelo:     AUC {a['auc']}  PR-AUC {a['pr_auc']}  F1 {a['f1']}  recall {a['recall']}  Brier {a['brier']}")
        print(f"  Línea base ({m['linea_base_nombre']}): AUC {b['auc']}  F1 {b['f1']}  recall {b['recall']}")
        print(f"  Casos: {m['casos']} | brote nuevo: {m['subconjuntos']['anticipacion_brote_nuevo']}")
        print("  Evaluación progresiva (entrena con todo lo anterior):")
        for r in m["evaluacion_progresiva"]:
            print(f"    {r['anio']}: tasa de brote {r['tasa_brote']:.0%} | AUC {r['auc']} | Brier {r['brier']} (sin información: {r['brier_sin_informacion']}) | MAE casos {r['mae_casos_p50']} | rango acierta {r['cobertura_p10_p90']:.0%}")
    for variant, label in (("casos", "con casos"), ("clima", "solo clima")):
        print(f"\nOtras enfermedades ({label}): " + " · ".join(f"{d} AUC {mm['auc']}" for d, mm in simple_metrics[variant].items()))


if __name__ == "__main__":
    main()
