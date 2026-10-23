"""Paso 6 — Reentrenamiento "campeón contra retador".

Cada semana llegan datos nuevos. En vez de reemplazar el modelo a ciegas:

  1. CAMPEÓN: el modelo de evaluación (entrenado con 2015–2021), tal como está.
  2. RETADOR:  un modelo nuevo entrenado con TODO lo etiquetado hasta 26 semanas atrás.
  3. Se comparan en esas últimas 26 semanas, que NINGUNO de los dos vio al entrenar.
  4. El retador se promueve solo si mejora el Brier al menos 5% sin perder más de 0,01 de AUC.
     Si se promueve, se vuelve a ajustar con todos los datos etiquetados (incluidas esas 26 semanas).
  5. El resultado queda en reports/retrain.json y en el registro de experimentos.

Los modelos "de producción" (prefijo prod_) alimentan las predicciones de HOY.
Los replays de 2017 y 2023 siguen usando el campeón de evaluación: nunca vio esas epidemias.
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score

from config import DATA_PROCESSED, MODELS, REPORTS
from features import DENGUE_FEATURES, complete_rows
from train import PARAMS, export_onnx, fit_dengue_models, log_run, predict_cases

HOLDOUT_WEEKS = 26
MIN_BRIER_GAIN = 0.05
MAX_AUC_DROP = 0.01


def score(clf, regs, df):
    X = df[DENGUE_FEATURES].values
    p = clf.predict_proba(X)[:, 1]
    y = df.dengue_outbreak.values
    cases = predict_cases(regs, X)
    return {
        "brier": round(float(brier_score_loss(y, p)), 4),
        "auc": round(float(roc_auc_score(y, p)), 3) if 0 < y.sum() < len(y) else None,
        "mae_casos_p50": round(float(mean_absolute_error(df.dengue_next.values, cases["p50"])), 2),
        "cobertura_p10_p90": round(float(((df.dengue_next.values >= cases["p10"]) & (df.dengue_next.values <= cases["p90"])).mean()), 3),
        "prob_media": round(float(p.mean()), 3),
        "tasa_brote": round(float(y.mean()), 3),
        "n": int(len(df)),
    }


def decide(champion, challenger):
    """Regla de promoción, separada para poder probarla."""
    gain = 1 - challenger["brier"] / champion["brier"] if champion["brier"] else 0.0
    auc_ok = (challenger["auc"] is None or champion["auc"] is None
              or challenger["auc"] >= champion["auc"] - MAX_AUC_DROP)
    promote = gain >= MIN_BRIER_GAIN and auc_ok
    return promote, round(gain, 3)


def main():
    feats = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    data = complete_rows(feats)
    last = data.week.max()
    cut = last - pd.Timedelta(weeks=HOLDOUT_WEEKS)
    train_challenger, holdout = data[data.week <= cut], data[data.week > cut]

    champion = joblib.load(MODELS / "dengue.joblib")
    challenger_clf, challenger_regs = fit_dengue_models(train_challenger)

    m_champion = score(champion["clf"], champion["regs"], holdout)
    m_challenger = score(challenger_clf, challenger_regs, holdout)
    promote, gain = decide(m_champion, m_challenger)

    if promote:
        clf, regs = fit_dengue_models(data)  # se vuelve a ajustar con todo lo etiquetado
        bundle = {"clf": clf, "regs": regs, "features": DENGUE_FEATURES,
                  "base_rate": round(float(data.dengue_outbreak.mean()), 4)}
        trained_until = str(last.date())
    else:
        clf, regs, bundle = champion["clf"], champion["regs"], champion
        trained_until = "2021-12-27"
    bundle = {**bundle, "origen": "retador promovido" if promote else "campeón", "entrenado_hasta": trained_until}
    joblib.dump(bundle, MODELS / "dengue_prod.joblib")
    export_onnx(clf, regs, prefix="prod_")

    reason = (f"El retador mejora el Brier {gain * 100:.0f}% en las últimas {HOLDOUT_WEEKS} semanas (mínimo exigido {MIN_BRIER_GAIN * 100:.0f}%)."
              if promote else
              f"El retador no supera al campeón por el margen exigido (mejora de Brier {gain * 100:.0f}%, mínimo {MIN_BRIER_GAIN * 100:.0f}%).")
    report = {
        "generado": pd.Timestamp.now(tz="America/Lima").strftime("%Y-%m-%d %H:%M"),
        "ventana_comparacion": {"desde": str(holdout.week.min().date()), "hasta": str(holdout.week.max().date()), "semanas": HOLDOUT_WEEKS},
        "campeon": {"nombre": "evaluación (2015–2021)", **m_champion},
        "retador": {"nombre": f"entrenado hasta {cut.date()}", **m_challenger},
        "decision": "promovido" if promote else "se mantiene el campeón",
        "mejora_brier_pct": round(gain * 100, 1),
        "motivo": reason,
        "modelo_en_produccion": {"origen": bundle["origen"], "entrenado_hasta": trained_until},
        "regla": f"Se promueve si el Brier mejora ≥ {MIN_BRIER_GAIN * 100:.0f}% y el AUC no cae más de {MAX_AUC_DROP}.",
    }
    (REPORTS / "retrain.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log_run("gbm-dengue-retador", {**PARAMS, "entrenado_hasta": str(cut.date()), "filas_train": int(len(train_challenger)), "promovido": promote},
            {"brier_campeon": m_champion["brier"], "brier_retador": m_challenger["brier"], "mejora_brier_pct": report["mejora_brier_pct"]},
            [REPORTS / "retrain.json"])

    print(f"Campeón vs retador en {report['ventana_comparacion']['desde']} → {report['ventana_comparacion']['hasta']} ({m_champion['n']} filas)")
    for nombre, m in (("Campeón", m_champion), ("Retador", m_challenger)):
        print(f"  {nombre:8s} Brier {m['brier']:.4f}  AUC {m['auc']}  MAE {m['mae_casos_p50']}  cobertura {m['cobertura_p10_p90']}")
    print(f"Decisión: {report['decision'].upper()} — {reason}")


if __name__ == "__main__":
    main()
