"""Casos reales de vigilancia (CDC-MINSA) → serie semanal por distrito.

Entrada: los CSV que baja ingest_cases.py. Salida: una tabla (distrito × semana) por enfermedad.

Decisiones que importan (todas con evidencia en ml/reports/dataset_card.md):
  1. Semanas: el MINSA usa semanas epidemiológicas (domingo–sábado; la semana 1 contiene el 4 de enero).
     Nuestro clima va de lunes a domingo; cada semana epidemiológica se asigna al lunes siguiente a su domingo.
  2. El último año de cada archivo nacional se considera PROVISIONAL y no se usa: el CDC lo consolida con
     retraso (en Piura, 2025 trae 1 117 casos en el archivo nacional frente a 12 242 en el del Gobierno Regional).
     Cuando el archivo incluya un año nuevo, el año anterior pasa a usarse solo.
  3. Una semana sin filas dentro del periodo cubierto es CERO casos; fuera del periodo cubierto es DESCONOCIDO (NaN).
  4. El archivo regional de Piura (2025–2026) NO se mezcla con la serie nacional: se guarda aparte como contexto.
  5. Los distritos se cruzan por UBIGEO, no por nombre (el archivo trae la Ñ dañada).
"""
import json

import numpy as np
import pandas as pd

from config import DATA_PROCESSED, DATA_RAW, districts_frame

MINSA = DATA_RAW / "minsa"
DISEASES_REAL = ["dengue", "leptospirosis", "eda", "ira"]
SOURCE_LABEL = {
    "dengue": "CDC-MINSA · Vigilancia epidemiológica de dengue",
    "leptospirosis": "CDC-MINSA · Vigilancia epidemiológica de las zoonosis (leptospirosis)",
    "eda": "CDC-MINSA · Vigilancia epidemiológica de EDA",
    "ira": "CDC-MINSA · Vigilancia epidemiológica de IRA",
}


# ---------------------------------------------------------------------------------------------
# Semanas epidemiológicas
# ---------------------------------------------------------------------------------------------
def epi_week_start(year, week):
    """Domingo con el que empieza la semana epidemiológica `week` del año `year` (vectorizado)."""
    year, week = np.asarray(year), np.asarray(week)
    jan4 = pd.to_datetime(pd.Series(year).astype(str).values + "-01-04")
    first_sunday = jan4 - pd.to_timedelta((jan4.day_of_week + 1) % 7, unit="D")
    return first_sunday + pd.to_timedelta((week - 1) * 7, unit="D")


def epi_week_monday(year, week):
    """Lunes de nuestra semana (lunes–domingo) que corresponde a la semana epidemiológica."""
    return epi_week_start(year, week) + pd.Timedelta(days=1)


def to_ubigeo(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(6)


# ---------------------------------------------------------------------------------------------
# Lectura de cada archivo → conteos semanales por ubigeo
# ---------------------------------------------------------------------------------------------
def _finish(df, ubigeos, value="casos"):
    df = df[df.ubigeo.isin(ubigeos) & df.semana.between(1, 53)].copy()
    df["week"] = epi_week_monday(df.ano.values, df.semana.values)
    return df.groupby(["ubigeo", "week"], as_index=False)[value].sum()


def read_dengue(path, ubigeos):
    df = pd.read_csv(path, usecols=["ubigeo", "ano", "semana", "tipo_dx"], dtype={"ubigeo": str})
    df["ubigeo"] = to_ubigeo(df.ubigeo)
    df = df[df.tipo_dx.isin(["C", "P"])]  # confirmados y probables
    df["casos"] = 1
    return _finish(df, ubigeos), int(df.ano.max())


def read_leptospirosis(path, ubigeos):
    df = pd.read_csv(path, usecols=["ubigeo", "ano", "semana", "enfermedad", "tipo_dx"], dtype={"ubigeo": str})
    df["ubigeo"] = to_ubigeo(df.ubigeo)
    last = int(df.ano.max())
    df = df[(df.enfermedad == "LEPTOSPIROSIS") & df.tipo_dx.isin(["C", "P"])]
    df["casos"] = 1
    return _finish(df, ubigeos), last


def read_eda(path, ubigeos):
    df = pd.read_csv(path, usecols=["ubigeo", "ano", "semana", "episodios_men5", "episodios_may5"], dtype={"ubigeo": str})
    df["ubigeo"] = to_ubigeo(df.ubigeo)
    df["casos"] = df.episodios_men5.fillna(0) + df.episodios_may5.fillna(0)
    return _finish(df, ubigeos), int(df.ano.max())


def read_ira(path, ubigeos):
    """IRA total notificada = IRA sin neumonía + neumonías (menores de 5 y mayores de 60)."""
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype={"ubigeo": str},
                     usecols=["ubigeo", "ano", "semana", "ira_no_neumonia", "neumonias_men5", "neumonias_60mas"])
    df["ubigeo"] = to_ubigeo(df.ubigeo)
    df["casos"] = df.ira_no_neumonia.fillna(0) + df.neumonias_men5.fillna(0) + df.neumonias_60mas.fillna(0)
    return _finish(df, ubigeos), int(df.ano.max())


def read_gore_piura(path, ubigeos):
    """Dengue de la región Piura (Gobierno Regional), años 2025 en adelante. Devuelve (conteos, última semana completa)."""
    df = pd.read_csv(path, encoding="latin-1", usecols=["FECHA_CORTE", "UBIGEO", "ANO", "SEMANA_NOTIFICACION"])
    df = df.rename(columns={"UBIGEO": "ubigeo", "ANO": "ano", "SEMANA_NOTIFICACION": "semana"})
    df["ubigeo"] = to_ubigeo(df.ubigeo)
    cut = pd.to_datetime(str(int(df.FECHA_CORTE.max())), format="%Y%m%d")
    # la semana del corte está incompleta salvo que el corte caiga en sábado (último día de la semana epidemiológica)
    week_of_cut = ((cut - epi_week_start(cut.year, 1)[0]).days // 7) + 1
    complete = week_of_cut if cut.day_of_week == 5 else week_of_cut - 1
    df = df[(df.ano >= 2025) & (df.semana <= complete)] if cut.year == df.ano.max() else df[df.ano >= 2025]
    df["casos"] = 1
    out = _finish(df, ubigeos)
    return out, epi_week_monday(cut.year, complete)[0]


# ---------------------------------------------------------------------------------------------
# Tabla semanal completa
# ---------------------------------------------------------------------------------------------
READERS = {
    "dengue": ("dengue.csv", read_dengue),
    "leptospirosis": ("zoonosis.csv", read_leptospirosis),
    "eda": ("eda.csv", read_eda),
    "ira": ("ira.csv", read_ira),
}


def to_grid(counts, districts, weeks, covered_until):
    """Cuadrícula distrito × semana: ceros dentro del periodo cubierto, NaN después."""
    grid = pd.MultiIndex.from_product([districts.district_id, weeks], names=["district_id", "week"]).to_frame(index=False)
    grid = grid.merge(districts[["district_id", "ubigeo"]], on="district_id").merge(counts, on=["ubigeo", "week"], how="left")
    grid["casos"] = grid["casos"].fillna(0.0)
    grid.loc[grid.week > covered_until, "casos"] = np.nan
    return grid[["district_id", "week", "casos"]]


def build(weeks, drop_provisional_year=True, directory=MINSA):
    """Devuelve (tabla semanal con una columna por enfermedad, ficha de cobertura)."""
    districts = districts_frame()
    ubigeos = set(districts.ubigeo)
    weeks = sorted(pd.to_datetime(pd.Series(weeks)).unique())
    table = pd.DataFrame({"district_id": np.repeat(districts.district_id.values, len(weeks)), "week": np.tile(weeks, len(districts))})
    coverage = {}
    for name, (fname, reader) in READERS.items():
        counts, last_year = reader(directory / fname, ubigeos)
        # El año más reciente del archivo está incompleto: se usa hasta la última semana del año anterior
        first_week_last_year = epi_week_monday(last_year, 1)[0]
        covered = first_week_last_year - pd.Timedelta(days=7) if drop_provisional_year else epi_week_monday(last_year, 53)[0]
        counts = counts[counts.week <= covered]
        grid = to_grid(counts, districts, weeks, covered).rename(columns={"casos": name})
        table = table.merge(grid, on=["district_id", "week"], how="left")
        coverage[name] = {"fuente": SOURCE_LABEL[name], "hasta": str(pd.Timestamp(covered).date()),
                          "anio_provisional_descartado": last_year if drop_provisional_year else None,
                          "casos_total": int(counts.casos.sum())}
    # Contexto de Piura (no entra al entrenamiento)
    gore_path = directory / "dengue_piura_gore.csv"
    if gore_path.exists():
        gore, gore_until = read_gore_piura(gore_path, ubigeos)
        piura = districts[districts.department == "Piura"]
        g = to_grid(gore, piura, weeks, gore_until).rename(columns={"casos": "dengue_gore"})
        table = table.merge(g, on=["district_id", "week"], how="left")
        coverage["dengue_gore_piura"] = {"fuente": "Gobierno Regional de Piura · Casos de dengue en la región Piura",
                                         "desde": "2025-01-01", "hasta": str(pd.Timestamp(gore_until).date()),
                                         "casos_total": int(gore.casos.sum())}
        table.loc[table.week < pd.Timestamp("2025-01-01"), "dengue_gore"] = np.nan
    return table, coverage


def save_coverage(coverage):
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    (DATA_PROCESSED / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=1), encoding="utf-8")
