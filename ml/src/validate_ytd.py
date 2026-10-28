"""Prueba histórica de la calibración con el acumulado oficial del año y factores de HOY por departamento.

Salida: reports/calibration_ytd.json con
  - la prueba en 2022–2025 (antes y después del ajuste, por año),
  - los factores de hoy por departamento, calculados con el último informe de la sala situacional del CDC.
"""
import json

import joblib
import pandas as pd

import calibration_ytd as cy
from config import DATA_PROCESSED, MODELS, REPORTS, REFERENCE_DIR, districts_frame
from features import FEATURES
from real_cases import epi_week_monday
from retrain import PROD_FILE
from train import predict_cases


def predictions(feats, bundle, since=None):
    f = FEATURES["clima"]
    data = feats.dropna(subset=f).copy()
    if since:
        data = data[data.week > since]
    p = predict_cases(bundle["regs"], data[f].values.astype(float))
    data["p10"], data["p50"], data["p90"] = p["p10"], p["p50"], p["p90"]
    return data[["district_id", "week", "p10", "p50", "p90"]]


def main():
    D = districts_frame()
    dep_of = D.set_index("district_id").department.to_dict()
    feats = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    cases = pd.read_parquet(DATA_PROCESSED / "cases_weekly.parquet")[["district_id", "week", "dengue"]]
    both = cy.dept_weekly().merge(cy.pilot_weekly(cases, dep_of), on=["dep", "week"], how="outer").fillna(0)

    # 1) prueba histórica con el campeón de evaluación (entrenado solo hasta 2021)
    champion = joblib.load(MODELS / "dengue_clima.joblib")
    bt = cy.backtest(predictions(feats, champion, since="2021-12-31"), feats[["district_id", "week", "dengue_next"]], both, dep_of)
    out = {
        "regla": f"casos del departamento en el año × participación del piloto, contra lo previsto por el modelo para esas semanas; "
                 f"factor acotado a {cy.FACTOR_MIN}–{cy.FACTOR_MAX:g} y elevado a {cy.ALPHA} (ajuste amortiguado)",
        "rezago_semanas": cy.LAG_WEEKS, "prueba_2022_2025": bt,
    }

    # 2) factores de hoy
    report_csv = REFERENCE_DIR / "dengue_2026_filas_cdc.csv"
    meta_json = REFERENCE_DIR / "dengue_2026_distritos_cdc.meta.json"
    if report_csv.exists() and meta_json.exists():
        meta = json.loads(meta_json.read_text(encoding="utf-8"))
        report = pd.read_csv(report_csv)
        prod_path = MODELS / PROD_FILE["clima"]
        bundle = joblib.load(prod_path) if prod_path.exists() else champion
        year, se = int(meta["anio"]), int(meta["semana_epidemiologica"])
        week = epi_week_monday(year, se)[0]
        cur = cy.current_factors(predictions(feats, bundle, since=f"{year - 1}-12-01"), report, both, dep_of, week)
        out["hoy"] = {"informe": {"semana_epidemiologica": se, "anio": year, "url": meta["url"]}, "por_departamento": cur}
    else:
        out["hoy"] = None
        print("  (sin informe de la sala situacional: no hay factores de hoy)")
    (REPORTS / "calibration_ytd.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    t = bt["total"]
    print(f"  Prueba 2022-2025 (solo clima): observado/previsto {t['antes']['razon_observado_previsto']} → {t['despues']['razon_observado_previsto']}; "
          f"error por distrito {t['antes']['mae_por_distrito']} → {t['despues']['mae_por_distrito']}; "
          f"rango P10–P90 {t['antes']['cobertura_p10_p90']:.0%} → {t['despues']['cobertura_p10_p90']:.0%}")
    if out["hoy"]:
        for dep, v in out["hoy"]["por_departamento"].items():
            print(f"  Hoy {dep}: factor {v['factor']} (departamento {v['casos_departamento_2026']} casos; "
                  f"estimado en el piloto {v['casos_estimados_piloto']}; previsto por el modelo {v['casos_previstos_por_el_modelo']})")


if __name__ == "__main__":
    main()
