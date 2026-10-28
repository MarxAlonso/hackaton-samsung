"""Casos de dengue 2026 POR DISTRITO, de la sala situacional del CDC Perú (informe semanal en PDF).

Por qué existe: los CSV de datos abiertos del CDC llegan hasta 2025, pero cada semana el CDC publica un informe de
dengue con una tabla por distrito (casos acumulados del año anterior y del año en curso, tasa por 100 mil habitantes,
casos de la última semana y defunciones). Es el único dato oficial de 2026 por distrito que hay en línea.

Qué NO es: no es una serie semanal (solo el acumulado del año y los casos de la última semana), así que no alimenta
al modelo con casos recientes. Se usa para contrastar y calibrar (ver validate_sala.py y calibration.py).

Fuente: https://www.dge.gob.pe/portal/docs/vigilancia/sala/{año}/SE{semana}/dengue.pdf (CDC Perú, Ministerio de Salud).
Se prueba desde la semana epidemiológica actual hacia atrás hasta encontrar un PDF real: el sitio responde con una
página HTML cuando el informe aún no existe.
"""
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from config import DATA_RAW, ROOT, districts_frame
from real_cases import epi_week_start

URL = "https://www.dge.gob.pe/portal/docs/vigilancia/sala/{year}/SE{week}/dengue.pdf"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
RAW = DATA_RAW / "dge"
REFERENCE = ROOT / "reference"
DEPARTMENTS = {"PIURA": "Piura", "TUMBES": "Tumbes", "LAMBAYEQUE": "Lambayeque"}

NAME = r"([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9 .'-]*?)"
ROW = re.compile(rf"^{NAME}\s+(\d+)\s+(\d+,\d+)\s+(\d+,\d+)\s+(\d+)\s+(\d+,\d+)\s+(\d+,\d+)\s+(\d+)\s+(\d+)\s+(\d+,\d+)\s*$")


def norm(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def num(s):
    return float(str(s).replace(",", "."))


def current_epi_week(today=None):
    today = pd.Timestamp(today or dt.date.today())
    week = int(((today - epi_week_start(today.year, 1)[0]).days // 7) + 1)
    return today.year, max(week, 1)


def find_latest(year=None, week=None, session=None):
    """Devuelve (año, semana, bytes) del informe más reciente que exista."""
    y, w = (year, week) if year else current_epi_week()
    http = session or requests
    for wk in range(w + 1, max(w - 12, 0), -1):
        try:
            r = http.get(URL.format(year=y, week=wk), headers=HEADERS, timeout=90)
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.content[:5] == b"%PDF-":
            return y, wk, r.content
    return None


def parse_pdf(path):
    """Filas por distrito de Piura, Tumbes y Lambayeque. Devuelve (DataFrame, semana epidemiológica del informe)."""
    from pypdf import PdfReader
    rows, se = [], None
    for page in PdfReader(str(path)).pages:
        text = page.extract_text() or ""
        head = re.search(r"Dengue en el departamento de (\w+)", text)
        if not head or head.group(1).upper() not in DEPARTMENTS:
            continue
        dep = DEPARTMENTS[head.group(1).upper()]
        m = re.search(r"SE\s*(\d+)\s*-\s*2026", text)
        if m:
            se = int(m.group(1))
        for line in text.splitlines():
            m = ROW.match(line.strip())
            if not m:
                continue
            name, c25, p25, t25, c26, p26, t26, cse, defu, let = m.groups()
            rows.append({"department": dep, "name": name.strip(), "casos_2025": int(c25), "tia_2025": num(t25), "casos_2026": int(c26),
                         "tia_2026": num(t26), "casos_ultima_semana": int(cse), "defunciones_2026": int(defu), "letalidad_pct": num(let)})
    return pd.DataFrame(rows), se


def match_districts(df):
    """Une por departamento y nombre normalizado con los 47 distritos del piloto."""
    ours = districts_frame()
    ours["key"] = ours.department + "|" + ours.district.map(norm)
    df = df.assign(key=df.department + "|" + df.name.map(norm))
    out = ours[["district_id", "district", "department", "key"]].merge(df.drop(columns=["department"]), on="key", how="left")
    return out.drop(columns=["key", "name"])


def main(force=False):
    RAW.mkdir(parents=True, exist_ok=True)
    REFERENCE.mkdir(exist_ok=True)
    found = find_latest()
    if not found:
        print("  No se encontró ningún informe de dengue de la sala situacional (se conserva el último guardado).")
        return 1
    year, week, content = found
    pdf = RAW / f"dengue_sala_{year}_SE{week}.pdf"
    pdf.write_bytes(content)
    df, se = parse_pdf(pdf)
    if df.empty:
        print("  El informe no trae las tablas por distrito esperadas: se conserva el último guardado.")
        return 1
    df.to_csv(REFERENCE / "dengue_2026_filas_cdc.csv", index=False, encoding="utf-8")   # todas las filas, con «demás distritos»
    table = match_districts(df)
    got = int(table.casos_2026.notna().sum())
    table.insert(2, "semana_epidemiologica", se or week)
    table.to_csv(REFERENCE / "dengue_2026_distritos_cdc.csv", index=False, encoding="utf-8")
    meta = {"fuente": "CDC Perú, sala situacional de dengue (informe semanal en PDF)", "url": URL.format(year=year, week=week),
            "anio": year, "semana_epidemiologica": se or week, "descargado": str(dt.date.today()),
            "distritos_en_el_informe": int(len(df)), "distritos_del_piloto_con_dato": got,
            "nota": "Casos acumulados del año y de la misma semana del año anterior, por distrito. Confirmados y probables."}
    (REFERENCE / "dengue_2026_distritos_cdc.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  Informe SE {se or week} de {year}: {len(df)} distritos de Piura, Tumbes y Lambayeque; {got} de los 47 del piloto con dato.")
    missing = table[table.casos_2026.isna()].district.tolist()
    if missing:
        print("  Sin dato en el informe (no figuran con casos o el nombre no coincide):", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
