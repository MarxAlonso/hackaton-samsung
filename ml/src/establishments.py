"""Establecimientos de salud que más casos de dengue notifican en cada distrito de Piura.

Fuente: casos de dengue del Gobierno Regional de Piura (datos abiertos), que traen el establecimiento que notificó.
NO es una predicción por establecimiento: el modelo predice por distrito. Esto le dice a la DIRESA, dentro de un
distrito en riesgo, dónde se está concentrando la carga de atención, con la tendencia de las últimas semanas.
Solo existe para Piura y llega hasta el corte de la fuente (no está al día).
"""
import json
import re

import pandas as pd

from config import districts_frame
from real_cases import epi_week_start, to_ubigeo

WINDOW = 8  # semanas epidemiológicas completas que se comparan con las 8 anteriores
SMALL = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "EL"}
KEEP_UPPER = re.compile(r"^(I{1,3}|IV|V|[IVX]+-?\d*|II-\d|I-\d|KM|ESSALUD|IPRESS|[A-Z]\.[A-Z]\.)$")


def clean_name(raw):
    """'E.S. HOSP. CHULUCANAS' → 'Hospital Chulucanas'; 'E.S. TACALA' → 'E.S. Tacala' (sin el prefijo, un nombre como
    'Castilla' se confundiría con el distrito). Conserva números romanos, siglas y ESSALUD en mayúsculas."""
    s = re.sub(r"\s+", " ", str(raw).upper().strip())
    s = re.sub(r"^(E\.S\.|C\.S\.|P\.S\.)\s+(?=HOSP)", "", s)   # un hospital ya lo dice su nombre
    s = s.replace("HOSP.", "HOSPITAL").replace("NRA.", "NUESTRA").replace("STA.", "SANTA")
    words = []
    for i, w in enumerate(s.split(" ")):
        words.append(w if KEEP_UPPER.match(w) else (w.lower() if (w in SMALL and i) else w.capitalize()))
    return " ".join(words)


def build(path):
    df = pd.read_csv(path, encoding="utf-8", usecols=["FECHA_CORTE", "UBIGEO", "ANO", "CENTRO_SALUD", "SEMANA_NOTIFICACION"], low_memory=False)
    df["ubigeo"] = to_ubigeo(df.UBIGEO)
    cut = pd.to_datetime(str(int(df.FECHA_CORTE.max())), format="%Y%m%d")
    week_of_cut = ((cut - epi_week_start(cut.year, 1)[0]).days // 7) + 1
    complete = week_of_cut if cut.day_of_week == 5 else week_of_cut - 1
    df = df[(df.ANO == cut.year) & (df.SEMANA_NOTIFICACION <= complete)].copy()
    df["recent"] = df.SEMANA_NOTIFICACION > complete - WINDOW
    df["before"] = df.SEMANA_NOTIFICACION.between(complete - 2 * WINDOW + 1, complete - WINDOW)
    df["nombre"] = df.CENTRO_SALUD.map(clean_name)

    ids = districts_frame().set_index("ubigeo").district_id
    out = {}
    for ubigeo, d in df.groupby("ubigeo"):
        if ubigeo not in ids.index or d.recent.sum() < 10:
            continue
        g = d.groupby("nombre").agg(casos=("recent", "sum"), previas=("before", "sum"), anio=("recent", "size")).reset_index()
        total, total_prev = int(g.casos.sum()), int(g.previas.sum())
        g = g[g.casos > 0].sort_values("casos", ascending=False).head(5)
        out[ids[ubigeo]] = {
            "casos_ultimas_8_semanas": total,
            "casos_8_semanas_previas": total_prev,
            "establecimientos_que_notifican": int((d[d.recent].nombre.nunique())),
            "top": [{"nombre": r.nombre, "casos": int(r.casos), "pct": round(r.casos / total * 100),
                     "casos_previas": int(r.previas), "casos_anio": int(r.anio)} for r in g.itertuples()],
        }
    meta = {
        "fuente": "Gobierno Regional de Piura · casos de dengue notificados por establecimiento (datos abiertos)",
        "desde_semana_epi": f"{cut.year}-SE{complete - WINDOW + 1}", "hasta_semana_epi": f"{cut.year}-SE{complete}",
        "hasta": str((epi_week_start(cut.year, complete)[0] + pd.Timedelta(days=6)).date()),
        "nota": "Es la carga de notificación, no una predicción por establecimiento. Solo Piura; llega hasta el corte de la fuente.",
    }
    return {"meta": meta, "distritos": out}


if __name__ == "__main__":
    from config import DATA_RAW
    r = build(DATA_RAW / "minsa" / "dengue_piura_gore.csv")
    print(json.dumps(r["meta"], ensure_ascii=False, indent=1), len(r["distritos"]), "distritos")
    k = next(iter(r["distritos"]))
    print(k, json.dumps(r["distritos"][k], ensure_ascii=False, indent=1)[:900])
