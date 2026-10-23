"""Paso 1b — Descarga de los casos reales de vigilancia (CDC-MINSA, Plataforma Nacional de Datos Abiertos).

Fuente: https://www.datosabiertos.gob.pe  ·  Licencia: Open Data Commons Attribution (hay que citar la fuente).

Notas de acceso (verificadas):
  - El portal solo existe con "www." y rechaza clientes que no parecen un navegador: se envía un
    User-Agent de navegador y el Referer del portal.
  - El nombre del archivo cambia cada año (…_2000_2025.csv → …_2000_2026.csv), así que el enlace
    vigente se descubre desde la página de cada conjunto de datos; si eso falla se usa el último conocido.
  - Los archivos pesan ~400 MB en total: solo se vuelven a bajar si cambió su tamaño o su fecha de
    modificación (se compara con una ficha .meta.json guardada al lado).
"""
import json
import re
import sys
import time

import requests

from config import DATA_RAW

MINSA_DIR = DATA_RAW / "minsa"
PORTAL = "https://www.datosabiertos.gob.pe"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Referer": PORTAL + "/",
}

# nombre local → (página del conjunto de datos, enlace conocido si no se puede descubrir otro)
SOURCES = {
    "dengue": ("/dataset/vigilancia-epidemiol%C3%B3gica-de-dengue", "datos_abiertos_vigilancia_dengue_2000_2025_0.csv"),
    "eda": ("/dataset/vigilancia-epidemiol%C3%B3gica-de-enfermedad-diarreica-aguda-eda", "datos_abiertos_vigilancia_edas_2000_2025.csv"),
    "ira": ("/dataset/vigilancia-epidemiologica-de-infecciones-respiratorias-agudas-ira", "datos_abiertos_vigilancia_iras_2000_2025.csv"),
    "zoonosis": ("/dataset/vigilancia-epidemiol%C3%B3gica-de-las-zoonosis", "datos_abiertos_vigilancia_zoonosis_2000_2025_0.csv"),
    # Dengue de la región Piura con casos de 2026 (el archivo nacional llega hasta 2025)
    "dengue_piura_gore": ("/dataset/casos-de-dengue-en-la-regi%C3%B3n-piura-gobierno-regional-piura", "dataset_dengue_actualizado.csv"),
}


def discover_url(page: str, fallback: str) -> str:
    """Busca en la página del conjunto el enlace .csv vigente."""
    try:
        r = requests.get(PORTAL + page, headers=HEADERS, timeout=40)
        r.raise_for_status()
        links = re.findall(r'href="([^"]+/sites/default/files/[^"]+\.csv)"', r.text)
        if links:
            url = links[0]
            return url if url.startswith("http") else PORTAL + url
    except requests.RequestException as exc:
        print(f"    (no se pudo leer la página: {type(exc).__name__}; se usa el enlace conocido)")
    return f"{PORTAL}/sites/default/files/{fallback}"


def remote_info(url: str) -> dict:
    r = requests.head(url, headers=HEADERS, timeout=40, allow_redirects=True)
    r.raise_for_status()
    return {"url": url, "bytes": int(r.headers.get("Content-Length", 0)), "modificado": r.headers.get("Last-Modified", "")}


def download(url: str, target) -> None:
    tmp = target.with_suffix(".part")
    with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(target)


def sync(force: bool = False) -> dict:
    MINSA_DIR.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, (page, fallback) in SOURCES.items():
        target, meta_path = MINSA_DIR / f"{name}.csv", MINSA_DIR / f"{name}.meta.json"
        try:
            remote = remote_info(discover_url(page, fallback))
        except requests.RequestException as exc:
            if target.exists():
                print(f"  {name}: sin conexión con el portal ({type(exc).__name__}); se usa la copia local")
                report[name] = {"estado": "copia local", **(json.loads(meta_path.read_text()) if meta_path.exists() else {})}
                continue
            raise
        known = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        fresh = target.exists() and known.get("bytes") == remote["bytes"] and known.get("modificado") == remote["modificado"]
        if fresh and not force:
            print(f"  {name}: al día ({remote['bytes'] / 1e6:.0f} MB, {remote['modificado']})")
            report[name] = {"estado": "al día", **remote}
            continue
        print(f"  {name}: descargando {remote['bytes'] / 1e6:.0f} MB desde {remote['url'].rsplit('/', 1)[-1]} …")
        t0 = time.time()
        download(remote["url"], target)
        if target.stat().st_size != remote["bytes"] and remote["bytes"]:
            raise RuntimeError(f"{name}: la descarga quedó incompleta ({target.stat().st_size} de {remote['bytes']} bytes)")
        meta_path.write_text(json.dumps({**remote, "descargado": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1))
        print(f"    listo en {time.time() - t0:.0f} s")
        report[name] = {"estado": "descargado", **remote}
    return report


if __name__ == "__main__":
    print("Descargando casos reales del CDC-MINSA (datos abiertos)")
    sync(force="--force" in sys.argv)
