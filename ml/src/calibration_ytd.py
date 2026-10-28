"""Calibración con el ACUMULADO OFICIAL del año (para el modelo de solo clima).

Problema: con solo clima el modelo no conoce los casos recientes y se queda muy corto en las epidemias (en 2023 y 2024
lo observado fue 8 y 22 veces lo previsto). El factor de intensidad de calibration.py no sirve aquí: necesita resultados
de las últimas semanas, y los casos por distrito llegan con meses de retraso.

Idea: el CDC publica cada semana el total de casos del año por departamento. Con eso se estima cuántos casos ha tenido
el piloto en lo que va del año y se compara con lo que el modelo habría previsto para esas mismas semanas:

    estimado_piloto = participación_del_piloto × casos_del_departamento_en_el_año
    factor_bruto    = (estimado_piloto + ancla) / (previsto_por_el_modelo + ancla)      (acotado a 0,5–40)
    factor          = factor_bruto ^ 0,6                                               (ajuste amortiguado)

Por qué amortiguado: con el factor completo el sesgo se corregía pero el error por distrito empeoraba, porque el
reparto entre distritos del modelo no es bueno. Con exponente 0,6 el error baja, el rango P10–P90 se acerca al 80% y
el sesgo se reduce a la mitad (ver reports/calibration_ytd.json, con la prueba en 2022–2025).

La participación del piloto sale de los 3 años anteriores completos y el acumulado conocido llega con un rezago de
5 semanas (lo mismo que ocurre hoy con el informe del CDC).
"""
import numpy as np
import pandas as pd

from config import DATA_PROCESSED, DATA_RAW
from real_cases import epi_week_monday

DEPARTMENTS = ["Piura", "Tumbes", "Lambayeque"]
ALPHA = 0.6
FACTOR_MIN, FACTOR_MAX = 0.5, 40.0
ANCHOR = 20.0            # casos de "ancla": con muy pocos casos el factor no se dispara
LAG_WEEKS = 5            # semanas de rezago del dato oficial en la prueba histórica
SHARE_YEARS = 3          # años anteriores para estimar la participación del piloto
MIN_EPI_WEEK = 14        # antes de la semana 14 hay muy poco acumulado para calibrar
CACHE = DATA_PROCESSED / "dengue_dept_weekly.parquet"


def dept_weekly():
    """Casos de dengue por departamento y semana (todo el departamento, no solo el piloto), del archivo nacional del CDC."""
    csv = DATA_RAW / "minsa" / "dengue.csv"
    if CACHE.exists() and CACHE.stat().st_mtime >= csv.stat().st_mtime:
        return pd.read_parquet(CACHE)
    raw = pd.read_csv(csv, usecols=["departamento", "ano", "semana", "tipo_dx"], low_memory=False)
    raw = raw[raw.tipo_dx.isin(["C", "P"]) & raw.semana.between(1, 53)]
    raw["dep"] = raw.departamento.str.upper().str.strip().map({d.upper(): d for d in DEPARTMENTS})
    raw = raw.dropna(subset=["dep"])
    raw["week"] = epi_week_monday(raw.ano.values, raw.semana.values)
    out = raw.groupby(["dep", "week"]).size().rename("dept").reset_index()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CACHE, index=False)
    return out


def pilot_weekly(cases, dep_of):
    return (cases.assign(dep=cases.district_id.map(dep_of)).groupby(["dep", "week"]).dengue.sum().rename("pilot").reset_index())


def participation(both, dep, year):
    """Qué parte de los casos del departamento cae en los distritos del piloto (promedio de los 3 años anteriores)."""
    g = both[(both.dep == dep) & (both.week.dt.year >= year - SHARE_YEARS) & (both.week.dt.year <= year - 1)]
    return float(g.pilot.sum() / max(g.dept.sum(), 1))


def expected_weekly(pred, dep_of):
    """Casos esperados por semana y departamento. p50 es la suma de las 4 semanas siguientes al origen:
    para la semana w se promedian los orígenes de las 4 semanas anteriores."""
    exp = pred.set_index(["district_id", "week"]).p50.div(4).unstack(0)
    exp_w = sum(exp.shift(k) for k in range(1, 5)) / 4
    return exp_w.T.groupby(lambda d: dep_of[d]).sum().T


def factor(estimated_pilot, model_total):
    raw = float(np.clip((estimated_pilot + ANCHOR) / (model_total + ANCHOR), FACTOR_MIN, FACTOR_MAX))
    return raw ** ALPHA


def backtest(pred, feats, both, dep_of, years=(2022, 2023, 2024, 2025)):
    """Repite la calibración en el pasado: en cada semana de origen usa solo lo que se sabía (acumulado hasta 5 semanas antes).
    `pred` trae p10/p50/p90 del modelo de solo clima; `feats` trae dengue_next (lo que realmente pasó)."""
    exp_dep = expected_weekly(pred, dep_of)
    p = pred.set_index(["district_id", "week"])
    truth = feats.set_index(["district_id", "week"]).dengue_next
    rows = []
    for t in sorted(pred.week.unique()):
        t = pd.Timestamp(t)
        year = t.year
        if year not in years or (t - epi_week_monday(year, 1)[0]).days // 7 + 1 < MIN_EPI_WEEK:
            continue
        start, end = epi_week_monday(year, 1)[0], t - pd.Timedelta(weeks=LAG_WEEKS)
        for dep in DEPARTMENTS:
            dw = both[both.dep == dep].set_index("week")
            est = participation(both, dep, year) * dw.dept.loc[start:end].sum()
            k = factor(est, exp_dep[dep].loc[start:end].sum())
            ids = [d for d in p.xs(t, level="week").index if dep_of[d] == dep]
            sub = p.xs(t, level="week").loc[ids]
            y = truth.xs(t, level="week").reindex(ids)
            ok = y.notna()
            if not ok.any():
                continue
            for label, kk in (("antes", 1.0), ("despues", k)):
                rows.append({"anio": year, "tipo": label, "y": float(y[ok].sum()), "p50": float((sub.p50[ok] * kk).sum()),
                             "mae": float((y[ok] - sub.p50[ok] * kk).abs().sum()), "n": int(ok.sum()),
                             "cubre": int(((y[ok] >= sub.p10[ok] * kk) & (y[ok] <= sub.p90[ok] * kk)).sum()), "factor": k})
    R = pd.DataFrame(rows)

    def summarize(g):
        return {"razon_observado_previsto": round(float(g.y.sum() / max(g.p50.sum(), 1)), 2),
                "mae_por_distrito": round(float(g.mae.sum() / g.n.sum()), 1),
                "cobertura_p10_p90": round(float(g.cubre.sum() / g.n.sum()), 3)}

    by_year = []
    for year, g in R.groupby("anio"):
        row = {"anio": int(year), "factor_mediano": round(float(g[g.tipo == "despues"].factor.median()), 2)}
        for label in ("antes", "despues"):
            row[label] = summarize(g[g.tipo == label])
        by_year.append(row)
    return {"por_anio": by_year, "total": {label: summarize(R[R.tipo == label]) for label in ("antes", "despues")}}


def current_factors(pred_today, report, both, dep_of, report_week_monday):
    """Factores por departamento para HOY con el último informe del CDC. `report` trae casos_2026 por fila de distrito
    y departamento (incluye la fila «demás distritos», así que la suma es el total del departamento)."""
    exp_dep = expected_weekly(pred_today, dep_of)
    year = report_week_monday.year
    start = epi_week_monday(year, 1)[0]
    out = {}
    for dep in DEPARTMENTS:
        total = int(report.loc[report.department == dep, "casos_2026"].sum())
        share = participation(both, dep, year)
        model_total = float(exp_dep[dep].loc[start:report_week_monday].sum())
        est = share * total
        out[dep] = {"factor": round(factor(est, model_total), 3), "casos_departamento_2026": total,
                    "participacion_piloto": round(share, 3), "casos_estimados_piloto": round(est),
                    "casos_previstos_por_el_modelo": round(model_total)}
    return out
