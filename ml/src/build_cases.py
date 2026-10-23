"""Paso 2 — Tabla semanal de casos por distrito: reales (CDC-MINSA) + golpe de calor simulado.

Salida: data/processed/cases_weekly.parquet  (district_id, week, dengue, leptospirosis, eda, ira, golpe_calor, dengue_gore)
        data/processed/coverage.json          (hasta qué semana hay datos reales de cada enfermedad)
Los valores desconocidos (después del último dato real) son NaN, no cero.
"""
import pandas as pd

import real_cases
import simulate
from config import DATA_PROCESSED


def main():
    clim = simulate.climate_table()
    weeks = clim.week.unique()
    table, coverage = real_cases.build(weeks)
    heat = clim[["district_id", "week"]].assign(golpe_calor=simulate.simulate_heat(clim).astype(float))
    table = table.merge(heat, on=["district_id", "week"], how="left")
    coverage["golpe_calor"] = {"fuente": "Simulado a partir de la temperatura máxima real (no hay fuente abierta)", "hasta": str(table.week.max().date())}
    cols = ["district_id", "week", "dengue", "leptospirosis", "eda", "ira", "golpe_calor", "dengue_gore"]
    table[cols].to_parquet(DATA_PROCESSED / "cases_weekly.parquet", index=False)
    real_cases.save_coverage(coverage)

    print("Casos REALES del CDC-MINSA en los 47 distritos del piloto (por año):")
    y = table.assign(anio=table.week.dt.year).groupby("anio")[["dengue", "leptospirosis", "eda", "ira"]].sum(min_count=1)
    print(y.loc[2015:2026].map(lambda v: "sin dato" if pd.isna(v) else f"{int(v):,}").to_string())
    print()
    for name, c in coverage.items():
        extra = f" ({c['ultima_semana_epidemiologica']})" if c.get("ultima_semana_epidemiologica") else ""
        print(f"  {name:18s} datos hasta {c['hasta']}{extra}")


if __name__ == "__main__":
    main()
