"""El optimizador debe respetar el presupuesto, no superar la cobertura total y ser realmente óptimo."""
import random
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # noqa: E402
from optimizer import optimize  # noqa: E402
from scoring import plan_inputs  # noqa: E402

client = TestClient(app)


def toy(n=8, seed=1):
    rnd = random.Random(seed)
    return [{"district_id": f"d{i}", "distrito": f"D{i}", "poblacion": rnd.randint(5000, 90000), "prob": rnd.random(),
             "casos_p10": (a := rnd.randint(0, 200)), "casos_p50": a + rnd.randint(0, 100), "casos_p90": a + 150 + rnd.randint(0, 300)}
            for i in range(n)]


def dp_best(districts, budget, hab, efect, key):
    """Programación dinámica exacta: máximo de casos evitados con asignaciones enteras."""
    import math
    best = [0.0] * (budget + 1)
    for d in districts:
        need = max(1, math.ceil(d["poblacion"] / hab))
        unit = efect * d[key] / need
        new = best[:]
        for b in range(budget + 1):
            for k in range(1, min(need, b) + 1):
                new[b] = max(new[b], best[b - k] + unit * k)
        best = new
    return best[budget]


def test_respeta_presupuesto_y_cobertura():
    for budget in (0, 3, 12, 40, 500):
        r = optimize(toy(), budget)
        assert r["optimo"]["total"]["brigadas"] <= budget
        assert all(0 <= x["cobertura"] <= 1 for x in r["optimo"]["distritos"])


def test_cero_brigadas_no_evita_nada():
    t = optimize(toy(), 0)["optimo"]["total"]
    assert t["evitados_p50"] == 0 and t["distritos_cubiertos"] == 0


def test_igual_a_la_programacion_dinamica():
    for seed in range(6):
        ds = toy(7, seed)
        for budget in (4, 9, 17):
            for criterio, key in (("probable", "casos_p50"), ("prudente", "casos_p90")):
                got = optimize(ds, budget, 15000, 0.3, criterio)["optimo"]["total"]["evitados_" + key[-3:]]
                assert abs(got - dp_best(ds, budget, 15000, 0.3, key)) < 1e-6, (seed, budget, criterio)


def test_optimo_no_pierde_contra_las_otras_reglas():
    for seed in range(10):
        e = optimize(toy(10, seed), 14)["estrategias"]
        assert e["optimo"]["evitados_p50"] >= e["por_probabilidad"]["evitados_p50"] - 1e-9
        assert e["optimo"]["evitados_p50"] >= e["parejo"]["evitados_p50"] - 1e-9


def test_mas_brigadas_nunca_evitan_menos():
    ds = toy(9, 3)
    vals = [optimize(ds, b)["optimo"]["total"]["evitados_p50"] for b in range(0, 40, 4)]
    assert vals == sorted(vals)


def test_parametros_invalidos():
    for bad in ({"brigadas": -1}, {"hab_por_brigada": 0}, {"efectividad": 1.5}):
        try:
            optimize(toy(), **{"brigadas": 5, **bad})
        except ValueError:
            continue
        raise AssertionError(f"debió rechazar {bad}")


def test_economia_opcional():
    r = optimize(toy(), 10, costo_brigada=8000, costo_caso=500)
    assert set(r["economia"]) == {"gasto", "ahorro", "neto", "ahorro_por_sol"}
    assert "economia" not in optimize(toy(), 10)


def test_endpoint_optimize():
    r = client.post("/optimize", json={"escenario": "2023", "brigadas": 20})
    assert r.status_code == 200
    body = r.json()
    assert body["optimo"]["total"]["brigadas"] <= 20
    assert body["estrategias"]["optimo"]["evitados_p50"] >= body["estrategias"]["parejo"]["evitados_p50"] - 1e-9
    assert len(plan_inputs("2023")) == 47


def test_endpoint_optimize_filtra_departamento_y_valida():
    r = client.post("/optimize", json={"departamento": "Tumbes", "brigadas": 5})
    assert r.status_code == 200 and all(x["district_id"].startswith("tum-") for x in r.json()["optimo"]["distritos"])
    assert client.post("/optimize", json={"brigadas": -2}).status_code == 422
    assert client.post("/optimize", json={"departamento": "Lima"}).status_code == 422
