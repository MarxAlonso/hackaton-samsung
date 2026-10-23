"""Calibración de la intensidad, intervalos de confianza y contexto de Piura."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import calibration  # noqa: E402
import establishments  # noqa: E402

REPORTS = Path(__file__).resolve().parents[1] / "reports"


def _weekly(values):
    idx = pd.date_range("2023-01-02", periods=len(values), freq="W-MON")
    return pd.Series(values, index=idx)


def test_el_factor_solo_usa_semanas_cuyo_resultado_ya_se_conocia():
    obs, pred = _weekly([10] * 20), _weekly([10] * 20)
    obs.iloc[-3:] = 1000          # lo que pasa en las últimas semanas aún NO se conoce en la semana de referencia
    week = obs.index[-1]
    assert calibration.intensity_factor(obs, pred, week) == 1.0  # esas 3 semanas de 1000 no cuentan


def test_el_factor_corrige_una_subestimacion_y_esta_acotado():
    obs, pred = _weekly([30] * 12), _weekly([10] * 12)
    f = calibration.intensity_factor(obs, pred, obs.index[-1])
    assert 1.5 < f <= calibration.FACTOR_MAX
    assert calibration.intensity_factor(_weekly([1000] * 12), pred, obs.index[-1]) == calibration.FACTOR_MAX
    assert calibration.intensity_factor(_weekly([0] * 12), pred, obs.index[-1]) == calibration.FACTOR_MIN


def test_sin_historia_el_factor_es_neutro():
    assert calibration.intensity_factor(_weekly([5, 5]), _weekly([5, 5]), pd.Timestamp("2023-01-09")) == 1.0


def test_bootstrap_remuestrea_distritos_y_el_intervalo_contiene_el_valor():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"district_id": np.repeat([f"d{i}" for i in range(20)], 30), "x": rng.normal(10, 2, 600)})
    ic = calibration.bootstrap_by_district(df, lambda d: {"media": d.x.mean()}, n_boot=100)
    lo, hi = ic["media"]
    assert lo < df.x.mean() < hi and ic["_n_remuestreos"] == 100


def test_nombres_de_establecimientos_se_limpian():
    assert establishments.clean_name("E.S. HOSP. CHULUCANAS") == "Hospital Chulucanas"
    assert establishments.clean_name("HOSPITAL III JOSE CAYETANO HEREDIA - ESSALUD") == "Hospital III Jose Cayetano Heredia - ESSALUD"
    assert establishments.clean_name("E.S. 9 DE OCTUBRE") == "E.S. 9 de Octubre"
    assert establishments.clean_name("E.S. CASTILLA") == "E.S. Castilla"


def test_la_calibracion_mejora_el_sesgo_en_las_epidemias():
    m = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))["dengue"]["calibracion_intensidad"]
    by = {r["anio"]: r for r in m["por_anio"]}
    for year in (2023, 2024):  # los años de epidemia que el modelo no vio
        assert abs(by[year]["razon_observado_previsto_despues"] - 1) < abs(by[year]["razon_observado_previsto_antes"] - 1)
        assert by[year]["cobertura_p10_p90_despues"] >= by[year]["cobertura_p10_p90_antes"]


def test_los_intervalos_de_confianza_incluyen_la_estimacion():
    m = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))
    for key in ("dengue", "dengue_clima"):
        ic = m[key]["intervalos_95"]
        assert ic["auc"][0] <= m[key]["modelo"]["auc"] <= ic["auc"][1]
        assert ic["cobertura_p10_p90"][0] <= m[key]["casos"]["cobertura_p10_p90"] <= ic["cobertura_p10_p90"][1]


def test_validacion_externa_documenta_el_resultado_de_la_senal_de_arrastre():
    v = json.loads((REPORTS / "validation_gore.json").read_text(encoding="utf-8"))
    assert v["ordenamiento"]["auc_modelo_clima"] > v["ordenamiento"]["auc_linea_base_calendario"]
    a = v["arrastre"]
    assert len(a["mejora_auc_ic95"]) == 2 and a["conclusion"]
    # si el intervalo incluye el cero, la señal NO debe presentarse como mejora
    if a["mejora_auc_ic95"][0] <= 0:
        assert "NO se integra" in a["conclusion"]
