"""Qué viene en 2027: pronósticos de El Niño de NOAA (Estados Unidos), descargados por script.

Tres fuentes públicas del Climate Prediction Center (CPC) de NOAA:
  1. Probabilidades oficiales de fuerza de El Niño / La Niña por temporada de 3 meses (tabla HTML, se actualiza el
     segundo jueves de cada mes). Es el pronóstico OFICIAL de NOAA; mide la región Niño 3.4 (Pacífico central) con el
     índice RONI, que es como NOAA define El Niño "global".
  2. Pronóstico del modelo CFSv2 para la región Niño 1+2 (el mar frente a Perú y Ecuador): 40 miembros por mes objetivo
     (archivo NetCDF). El miembro 41 trae el valor observado de los meses pasados. Se guarda media, P10 y P90 por mes.
  3. La discusión diagnóstica mensual (texto): fecha, estado del sistema de alerta y la frase de síntesis.
Además, el valor observado mensual de Niño 1+2 (índice relativo, archivo rel_mthsst9120.txt).

Lo que NO es: NOAA no pronostica "El Niño costero" tal como lo define el Perú; eso lo hace el ENFEN. Se muestran las dos
cosas juntas y así se dice en el sitio. Salida: ml/reference/enso_outlook.json. Si algo falla, se conserva el último.
"""
import datetime as dt
import html as htmlmod
import json
import re
import sys

import numpy as np
import requests

from config import REFERENCE_DIR

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
URL_STRENGTH = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/strengths/"
URL_DISC = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
URL_CFS_NINO12 = "https://www.cpc.ncep.noaa.gov/products/CFSv2/dataInd1/nino12Mon.nc"
URL_OBS = "https://www.cpc.ncep.noaa.gov/data/indices/rel_mthsst9120.txt"
OUT = REFERENCE_DIR / "enso_outlook.json"
SEASONS = {"JFM": (1, 3), "FMA": (2, 4), "MAM": (3, 5), "AMJ": (4, 6), "MJJ": (5, 7), "JJA": (6, 8), "JAS": (7, 9), "ASO": (8, 10),
           "SON": (9, 11), "OND": (10, 12), "NDJ": (11, 1), "DJF": (12, 2)}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_EN = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}


def get(url, binary=False):
    r = requests.get(url, headers=HEADERS, timeout=90)
    r.raise_for_status()
    return r.content if binary else r.text


def text_of(page):
    page = re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)
    return htmlmod.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))


def season_label(code, issued_year, issued_month, index):
    """Las 9 temporadas van en orden: la primera empieza el mes anterior al de emisión (p. ej. emitido en octubre → SON)."""
    m1, m2 = SEASONS[code]
    start = issued_month - 1 + index          # mes de inicio en una escala continua
    y1 = issued_year + (start - 1) // 12
    assert (start - 1) % 12 + 1 == m1, f"la temporada {code} no sigue el orden esperado"
    y2 = y1 if m2 >= m1 else y1 + 1
    return f"{MESES[m1 - 1]} {y1} – {MESES[m2 - 1]} {y2}", y1, m1


def parse_strength(page):
    """Tabla oficial: por temporada, probabilidad (%) de cada categoría de fuerza (9 columnas, de La Niña fuerte a El Niño muy fuerte)."""
    txt = text_of(page)
    issued = re.search(r"Issued ([A-Z][a-z]+) (\d{4})(?!\s*-->)", txt)
    # la página deja un "Issued abril 2026 -->" dentro de un comentario: se toma la última emisión que aparece en el texto
    issues = re.findall(r"Issued ([A-Z][a-z]+) (\d{4})", txt)
    month_name, year = issues[-1] if issues else (issued.group(1), issued.group(2))
    iy, im = int(year), MONTHS_EN[month_name]
    rows = []
    for m in re.finditer(r"\b([A-Z]{3}) [A-Z][a-z]{2} [A-Z][a-z]{2} [A-Z][a-z]{2}((?: \d{1,3}){9})\b", txt):
        code = m.group(1)
        if code not in SEASONS:
            continue
        v = [int(x) for x in m.group(2).split()]
        label, y1, m1 = season_label(code, iy, im, len(rows))
        la_nina, neutral, el_nino = sum(v[:4]), v[4], sum(v[5:])
        rows.append({"temporada": code, "etiqueta": label, "inicio": f"{y1}-{m1:02d}",
                     "la_nina_pct": la_nina, "neutral_pct": neutral, "el_nino_pct": el_nino,
                     "el_nino_por_fuerza_pct": {"debil": v[5], "moderado": v[6], "fuerte": v[7], "muy_fuerte": v[8]}})
    return {"emitido": f"{iy}-{im:02d}", "fuente": "NOAA CPC, Official ENSO Strength Probabilities (índice RONI, región Niño 3.4)",
            "url": URL_STRENGTH, "temporadas": rows}


def parse_discussion(page):
    txt = text_of(page)
    status = re.search(r"ENSO Alert System Status:\s*([^S]+?)\s+Synopsis", txt)
    synopsis = re.search(r"Synopsis:\s*(.+?)\s+(?:El Niño|La Niña|ENSO-neutral) (?:continued|strengthened|conditions|persisted|weakened)", txt)
    issued = re.search(r"issued by[^0-9]*(\d{1,2} [A-Z][a-z]+ \d{4})", txt) or re.search(r"(\d{1,2} [A-Z][a-z]+ \d{4})", txt)
    nxt = re.search(r"next ENSO Diagnostics Discussion is scheduled for (\d{1,2} [A-Z][a-z]+ \d{4})", txt)
    historic = re.search(r"(\d+)% for ([A-Z][a-z]+-[A-Z][a-z]+), (\d+)% for ([A-Z][a-z]+-[A-Z][a-z]+), and (\d+)% for ([A-Z][a-z]+-[A-Z][a-z]+)", txt)
    indices = re.search(r"\+?(-?\d\.\d)°C in Niño-3\.4, \+?(-?\d\.\d)°C in Niño-3, and \+?(-?\d\.\d)°C in Niño-1\+2", txt)
    out = {"fuente": "NOAA CPC, ENSO Diagnostic Discussion", "url": URL_DISC,
           "estado_alerta": status.group(1).strip() if status else None,
           "sintesis_en": synopsis.group(1).strip() if synopsis else None,
           "proxima_discusion": nxt.group(1) if nxt else None}
    if issued:
        try:
            d, mo, y = issued.group(1).split()
            out["emitido"] = f"{y}-{MONTHS_EN[mo]:02d}-{int(d):02d}"
        except (KeyError, ValueError):
            out["emitido"] = None
    if historic:
        out["evento_historico"] = {"definicion": "RONI de 3 meses de +2,5 °C o más: superaría todos los El Niño desde 1950",
                                   "probabilidades_pct": {historic.group(2): int(historic.group(1)), historic.group(4): int(historic.group(3)), historic.group(6): int(historic.group(5))}}
    if indices:
        out["indices_ultimo_mes_C"] = {"nino34": float(indices.group(1)), "nino3": float(indices.group(2)), "nino12": float(indices.group(3))}
    return out


def parse_cfs(content):
    import netCDF4
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp()) / "nino12Mon.nc"
    tmp.write_bytes(content)
    d = netCDF4.Dataset(str(tmp))
    a = np.array(d.variables["anom"][:])[:, :, 0, 0, 0]
    a[a < -999] = np.nan
    base = dt.date(2021, 1, 1)
    months = [base + dt.timedelta(days=int(x)) for x in d.variables["time"][:]]
    created = getattr(d, "history", "")
    obs, fc = [], []
    for i, m in enumerate(months):
        members = a[:40, i]
        ok = members[~np.isnan(members)]
        if len(ok) >= 10:
            fc.append({"mes": m.strftime("%Y-%m"), "media": round(float(ok.mean()), 2), "p10": round(float(np.percentile(ok, 10)), 2),
                       "p90": round(float(np.percentile(ok, 90)), 2), "miembros": int(len(ok))})
        elif not np.isnan(a[40, i]):
            obs.append({"mes": m.strftime("%Y-%m"), "valor": round(float(a[40, i]), 2)})
    m = re.search(r"created: (\d{4}-\d{2}-\d{2})", created)
    return {"fuente": "NOAA CPC, modelo CFSv2 (40 miembros), anomalía mensual de la región Niño 1+2 frente a Perú y Ecuador",
            "url": URL_CFS_NINO12, "generado": m.group(1) if m else None, "observado": obs, "pronostico": fc}


def parse_obs(txt):
    rows = []
    for line in txt.splitlines():
        p = line.split()
        if len(p) >= 6 and p[0].isdigit() and p[1].isdigit():
            rows.append({"mes": f"{p[0]}-{int(p[1]):02d}", "nino12": float(p[2]), "nino3": float(p[3]), "nino4": float(p[4]), "nino34": float(p[5])})
    return {"fuente": "NOAA CPC, índices Niño mensuales relativos (rel_mthsst9120.txt)", "url": URL_OBS, "ultimos": rows[-15:]}


def main():
    REFERENCE_DIR.mkdir(exist_ok=True)
    out = {"descargado": str(dt.date.today()), "nota": "NOAA pronostica El Niño global (Niño 3.4) y el mar frente a Perú (Niño 1+2); "
           "el aviso oficial de El Niño costero en el Perú lo emite el ENFEN."}
    errors = []
    for key, fn in (("probabilidades_oficiales", lambda: parse_strength(get(URL_STRENGTH))),
                    ("discusion", lambda: parse_discussion(get(URL_DISC))),
                    ("cfsv2_nino12", lambda: parse_cfs(get(URL_CFS_NINO12, binary=True))),
                    ("observado", lambda: parse_obs(get(URL_OBS)))):
        try:
            out[key] = fn()
        except Exception as exc:  # una fuente caída no debe tumbar las demás
            errors.append(f"{key}: {type(exc).__name__}: {exc}")
    ok = out.get("probabilidades_oficiales", {}).get("temporadas") and out.get("cfsv2_nino12", {}).get("pronostico")
    if not ok:
        print("  No se pudo leer el pronóstico de NOAA (se conserva el último):", "; ".join(errors))
        return 1
    if errors:
        print("  Avisos:", "; ".join(errors))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    p = out["probabilidades_oficiales"]
    fc = out["cfsv2_nino12"]["pronostico"]
    peak = max(fc, key=lambda r: r["media"])
    print(f"  NOAA: probabilidades emitidas {p['emitido']}, {len(p['temporadas'])} temporadas; CFSv2 Niño 1+2: {len(fc)} meses, "
          f"máximo {peak['media']} °C en {peak['mes']}; discusión: {out.get('discusion', {}).get('estado_alerta')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
