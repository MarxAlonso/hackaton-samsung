"""Casos 2026 por distrito (informe del CDC) y calibración con el acumulado oficial del año."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import calibration_ytd as cy  # noqa: E402
import ingest_dge_sala as dge  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_lee_una_fila_de_la_tabla_del_informe():
    m = dge.ROW.match("TAMBO GRANDE 42 4,06 32,76 2433 20,79 1889,11 112 3 0,12")
    assert m and m.group(1) == "TAMBO GRANDE" and m.group(5) == "2433" and m.group(9) == "3"
    assert dge.ROW.match("VEINTISEIS DE OCTUBRE 93 9,00 46,25 641 6,50 318,80 66 1 0,16")
    assert dge.ROW.match("DEMAS DISTRITOS 294 20,00 191,86 2092 15,00 191,86 208 1 0,05")
    # los encabezados y los números sueltos no son filas de distrito
    for line in ("125 121434072 79304 32246 1117", "2020 2021 2022 20242023 2025 2026*", "casos % TIA por 100 mil Hab."):
        assert dge.ROW.match(line) is None


def test_une_distritos_por_nombre_sin_tildes_ni_parentesis_y_por_departamento():
    assert dge.norm("Pariñas") == dge.norm("PARINAS")
    df = pd.DataFrame([{"department": "Piura", "name": "CASTILLA", "casos_2025": 209, "tia_2025": 1.0, "casos_2026": 612, "tia_2026": 307.4,
                        "casos_ultima_semana": 59, "defunciones_2026": 0, "letalidad_pct": 0.0},
                       {"department": "Tumbes", "name": "CASTILLA", "casos_2025": 1, "tia_2025": 1.0, "casos_2026": 1, "tia_2026": 1.0,
                        "casos_ultima_semana": 0, "defunciones_2026": 0, "letalidad_pct": 0.0}])
    out = dge.match_districts(df)
    assert out.loc[out.district_id == "piu-castilla", "casos_2026"].iloc[0] == 612   # el de Tumbes no se mezcla


def test_el_informe_guardado_es_coherente():
    meta = json.loads((ROOT / "reference" / "dengue_2026_distritos_cdc.meta.json").read_text(encoding="utf-8"))
    rows = pd.read_csv(ROOT / "reference" / "dengue_2026_filas_cdc.csv")
    assert meta["distritos_del_piloto_con_dato"] >= 15 and meta["url"].startswith("https://www.dge.gob.pe/")
    assert set(rows.department) == {"Piura", "Tumbes", "Lambayeque"}
    # la suma de las filas (con «demás distritos») es el total del departamento: Piura ya pasa de 10 mil casos en 2026
    assert rows[rows.department == "Piura"].casos_2026.sum() > 10_000
    assert (rows.casos_2026 >= 0).all() and rows.tia_2026.notna().all()


def test_el_factor_esta_acotado_y_amortiguado():
    assert cy.factor(0, 1_000_000) == cy.FACTOR_MIN ** cy.ALPHA                      # piso
    assert cy.factor(10**9, 1) == cy.FACTOR_MAX ** cy.ALPHA                          # techo
    assert 1.0 < cy.factor(1000, 100) < (1020 / 120)                                 # sube, pero menos que la razón cruda
    assert abs(cy.factor(500, 500) - 1.0) < 1e-9                                     # si el modelo acertó, no cambia nada
    assert cy.factor(2000, 100) > cy.factor(1000, 100)                               # monótono


def test_con_pocos_casos_el_factor_no_se_dispara():
    assert cy.factor(3, 0.2) < 1.2   # el ancla evita dividir por casi cero


def test_la_calibracion_con_el_acumulado_mejora_el_modelo_solo_clima_en_la_prueba_historica():
    r = json.loads((ROOT / "reports" / "calibration_ytd.json").read_text(encoding="utf-8"))
    t = r["prueba_2022_2025"]["total"]
    assert t["despues"]["razon_observado_previsto"] < t["antes"]["razon_observado_previsto"] / 2      # el sesgo baja a menos de la mitad
    assert t["despues"]["mae_por_distrito"] < t["antes"]["mae_por_distrito"]                          # y el error no empeora
    assert abs(t["despues"]["cobertura_p10_p90"] - 0.8) < abs(t["antes"]["cobertura_p10_p90"] - 0.8)  # el rango se acerca al 80%
    assert r["hoy"] and set(r["hoy"]["por_departamento"]) == {"Piura", "Tumbes", "Lambayeque"}


def test_los_factores_de_hoy_llegan_al_sitio_y_la_api():
    app = json.loads((ROOT.parent / "web" / "public" / "data" / "app.json").read_text(encoding="utf-8"))
    act = app["escenarios"]["actual"]
    assert act["ajuste_intensidad"]["origen"].startswith("acumulado oficial")
    factors = {d["district_id"][:3]: d["factor_intensidad"] for d in act["distritos"]}
    assert all(0.6 <= f <= cy.FACTOR_MAX ** cy.ALPHA + 1e-6 for f in factors.values())
    # el replay de 2023 no puede usar información de 2026
    assert "acumulado oficial" not in json.dumps(app["escenarios"]["2023"].get("ajuste_intensidad"))
    assert app["dengue_2026_cdc"]["distritos"]["piu-castilla"]["casos_2026"] > 0
