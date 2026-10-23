"""Casos mínimos de la sesión 13: válido, campo faltante, tipo incorrecto, valor extremo y salud."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_predict_valido():
    r = client.post("/predict", json={"district_id": "piu-castilla"})
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["riesgos"]["dengue"]["prob"] <= 1
    assert body["riesgos"]["dengue"]["casos_p10"] <= body["riesgos"]["dengue"]["casos_p90"]
    assert set(body["riesgos"]) == {"dengue", "leptospirosis", "eda", "golpe_calor", "ira"}


def test_mas_lluvia_no_baja_el_riesgo_de_dengue():
    seco = client.post("/predict", json={"district_id": "piu-castilla", "escenario": "actual"}).json()
    lluvia = client.post("/predict", json={"district_id": "piu-castilla", "lluvia_pct": 100}).json()
    assert lluvia["riesgos"]["dengue"]["prob"] >= seco["riesgos"]["dengue"]["prob"] - 0.05


def test_campo_faltante():
    assert client.post("/predict", json={}).status_code == 422


def test_tipo_incorrecto():
    assert client.post("/predict", json={"district_id": "piu-castilla", "lluvia_pct": "mucho"}).status_code == 422


def test_valor_extremo():
    assert client.post("/predict", json={"district_id": "piu-castilla", "lluvia_pct": 9999}).status_code == 422


def test_distrito_desconocido():
    assert client.post("/predict", json={"district_id": "no-existe"}).status_code == 404


def test_batch():
    r = client.post("/predict/batch", json={"items": [{"district_id": "piu-piura"}, {"district_id": "tum-tumbes"}]})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_predict_incluye_lluvias_extremas_y_modelo():
    body = client.post("/predict", json={"district_id": "tum-tumbes"}).json()
    assert body["lluvias_extremas"]["nivel"] in {"alto", "medio", "bajo"}
    assert body["lluvias_extremas"]["umbral_alto_mm"] > body["lluvias_extremas"]["umbral_medio_mm"]
    assert body["modelo"]["id"] == "prod"
    assert client.post("/predict", json={"district_id": "tum-tumbes", "escenario": "2023"}).json()["modelo"]["id"] == "eval"


def test_monitoreo():
    r = client.get("/monitoreo").json()
    assert r["monitoreo"]["estado"] in {"estable", "vigilar", "reentrenar"}
    assert r["reentrenamiento"]["decision"] in {"promovido", "se mantiene el campeón"}
