"""Paso 4 — Entrenamiento y evaluación.

Dengue (modelo principal):
  - Clasificador GradientBoosting → probabilidad de brote en las próximas 4 semanas.
  - 3 regresores cuantílicos → casos esperados: pesimista (P90), probable (P50), optimista (P10).
  - Línea base: canal endémico (si hoy está sobre el canal, predice brote) y "repetir las
    últimas 4 semanas" para los casos.
Otras enfermedades: regresión logística → probabilidad de "semanas de riesgo alto"
(casos de las próximas 4 semanas sobre el percentil 80 histórico del distrito).

Validación temporal: entrena con 2016–2021 y evalúa con 2022 en adelante (incluye la
epidemia de 2023, que el modelo nunca vio).
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
from features import DENGUE_FEATURES, SIMPLE_FEATURES, build, complete_rows

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}


def classification_metrics(y, proba, threshold=0.5):
    pred = (proba >= threshold).astype(int)
    return {
        "auc": round(float(roc_auc_score(y, proba)), 3),
        "pr_auc": round(float(average_precision_score(y, proba)), 3),
        "brier": round(float(brier_score_loss(y, proba)), 4),
        "f1": round(float(f1_score(y, pred)), 3),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 3),
        "recall": round(float(recall_score(y, pred)), 3),
    }


def reliability(y, proba, bins=10):
    """¿Cuando el modelo dice 70%, ocurre ~70% de las veces?"""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(proba, edges) - 1, 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = idx == b
        if mask.sum() >= 20:
            rows.append({"predicho": round(float(proba[mask].mean()), 3),
                         "observado": round(float(y[mask].mean()), 3), "n": int(mask.sum())})
    return rows


PARAMS = {"n_estimators_clf": 250, "n_estimators_reg": 300, "max_depth": 3, "lr_clf": 0.05, "lr_reg": 0.08, "subsample": 0.8}


def fit_dengue_models(train):
    """Ajusta el clasificador de brote y los 3 regresores de casos (P10/P50/P90)."""
    X_tr = train[DENGUE_FEATURES].values
    clf = GradientBoostingClassifier(n_estimators=PARAMS["n_estimators_clf"], max_depth=PARAMS["max_depth"],
                                     learning_rate=PARAMS["lr_clf"], subsample=PARAMS["subsample"], random_state=SEED)
    clf.fit(X_tr, train.dengue_outbreak.values)
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


def train_dengue(train, test):
    X_te = test[DENGUE_FEATURES].values
    y_te = test.dengue_outbreak.values

    clf, regs = fit_dengue_models(train)
    proba = clf.predict_proba(X_te)[:, 1]

    baseline_pred = ((test.inc_0 > test.canal_now) & (test.dengue >= 5)).astype(float).values
    metrics = {
        "modelo": classification_metrics(y_te, proba),
        "linea_base_canal_endemico": classification_metrics(y_te, baseline_pred),
        "confiabilidad": reliability(y_te, proba),
        "tasa_brote_test": round(float(y_te.mean()), 3),
    }
    # Subconjuntos difíciles: el AUC global se infla con semanas secas o distritos de altura
    season = ((test.inc_0_3 > 0) & test.week.dt.month.between(1, 6)).values
    onset = (test.inc_0 <= test.canal_now).values  # aún no hay brote: ¿lo anticipa?
    metrics["subconjuntos"] = {
        "temporada_con_casos": {"auc": round(float(roc_auc_score(y_te[season], proba[season])), 3),
                                "tasa_brote": round(float(y_te[season].mean()), 3), "n": int(season.sum())},
        "anticipacion_brote_nuevo": {
            "auc": round(float(roc_auc_score(y_te[onset], proba[onset])), 3),
            "pr_auc": round(float(average_precision_score(y_te[onset], proba[onset])), 3),
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
        ((f, round(float(v), 4)) for f, v in zip(DENGUE_FEATURES, clf.feature_importances_)),
        key=lambda kv: -kv[1]))
    return clf, regs, metrics


def train_simple(train, test):
    models, metrics = {}, {}
    for disease in DISEASES:
        if disease == "dengue":
            continue
        thresholds = train.groupby("district_id")[f"{disease}_next"].quantile(0.8)
        cols = SIMPLE_FEATURES

        def frame(df):
            X = df.assign(own_inc_0_3=np.log1p(df[f"{disease}_inc_0_3"]))[cols].values
            y = (df[f"{disease}_next"] > df.district_id.map(thresholds)).astype(int).values
            return X, y

        X_tr, y_tr = frame(train)
        X_te, y_te = frame(test)
        scaler = StandardScaler().fit(X_tr)
        lr = LogisticRegression(max_iter=2000, C=0.5).fit(scaler.transform(X_tr), y_tr)
        proba = lr.predict_proba(scaler.transform(X_te))[:, 1]
        metrics[disease] = classification_metrics(y_te, proba)
        models[disease] = {
            "features": cols,
            "mean": scaler.mean_.round(6).tolist(),
            "scale": scaler.scale_.round(6).tolist(),
            "coef": lr.coef_[0].round(6).tolist(),
            "intercept": round(float(lr.intercept_[0]), 6),
            "base_rate": round(float(y_tr.mean()), 4),
            "threshold_by_district": thresholds.round(1).to_dict(),
        }
    return models, metrics


def export_onnx(clf, regs, prefix=""):
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    import onnxruntime as ort

    n = len(DENGUE_FEATURES)
    initial = [("features", FloatTensorType([None, n]))]
    onnx_clf = convert_sklearn(clf, initial_types=initial, options={id(clf): {"zipmap": False}},
                               target_opset=17)
    (MODELS / f"{prefix}dengue_outbreak.onnx").write_bytes(onnx_clf.SerializeToString())
    for name, reg in regs.items():
        onnx_reg = convert_sklearn(reg, initial_types=initial, target_opset=17)
        (MODELS / f"{prefix}dengue_cases_{name}.onnx").write_bytes(onnx_reg.SerializeToString())

    # Verificación: ONNX y scikit-learn deben dar lo mismo
    sample = np.random.default_rng(0).normal(size=(5, n)).astype(np.float32) * 10 + 20
    sess = ort.InferenceSession(str(MODELS / f"{prefix}dengue_outbreak.onnx"))
    onnx_proba = sess.run(None, {"features": sample})[1][:, 1]
    diff = np.abs(onnx_proba - clf.predict_proba(sample)[:, 1]).max()
    print(f"  ONNX vs sklearn, diferencia máxima: {diff:.2e}")
    assert diff < 1e-4


def log_run(name, params, metrics, artifacts=()):
    """Registra cada entrenamiento: siempre en reports/experiments.jsonl (sirve en CI sin dependencias)
    y, si MLflow está instalado, también en ml/mlruns/ (`mlflow ui` para verlo)."""
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

    data = complete_rows(feats)
    train = data[data.week <= TRAIN_END]
    test = data[data.week > TRAIN_END]
    print(f"Entrenamiento: {len(train):,} filas | Prueba: {len(test):,} filas")

    clf, regs, dengue_metrics = train_dengue(train, test)
    simple_models, simple_metrics = train_simple(train, test)
    metrics = {"dengue": dengue_metrics, "otras_enfermedades": simple_metrics,
               "periodo_entrenamiento": f"{train.week.min().date()} a {train.week.max().date()}",
               "periodo_prueba": f"{test.week.min().date()} a {test.week.max().date()}"}

    joblib.dump({"clf": clf, "regs": regs, "features": DENGUE_FEATURES,
                 "base_rate": round(float(train.dengue_outbreak.mean()), 4)}, MODELS / "dengue.joblib")
    (MODELS / "simple_models.json").write_text(json.dumps(simple_models, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    export_onnx(clf, regs)
    m = dengue_metrics["modelo"]
    log_run("gbm-dengue-evaluacion", {**PARAMS, "train_end": TRAIN_END, "features": len(DENGUE_FEATURES), "filas_train": int(len(train))},
            {"auc": m["auc"], "pr_auc": m["pr_auc"], "brier": m["brier"], "f1": m["f1"], "recall": m["recall"],
             "mae_p50": dengue_metrics["casos"]["mae_modelo_p50"], "cobertura_p10_p90": dengue_metrics["casos"]["cobertura_p10_p90"]},
            [REPORTS / "metrics.json"])

    m, b = dengue_metrics["modelo"], dengue_metrics["linea_base_canal_endemico"]
    print(f"\nDengue — brote en 4 semanas (prueba {metrics['periodo_prueba']})")
    print(f"  Modelo:          AUC {m['auc']}  F1 {m['f1']}  recall {m['recall']}  Brier {m['brier']}")
    print(f"  Canal endémico:  AUC {b['auc']}  F1 {b['f1']}  recall {b['recall']}")
    print(f"  Casos: {dengue_metrics['casos']}")
    for d, mm in simple_metrics.items():
        print(f"  {d:14s} AUC {mm['auc']}  F1 {mm['f1']}")


if __name__ == "__main__":
    main()
