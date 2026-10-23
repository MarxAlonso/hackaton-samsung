"""Pruebas del pipeline de datos y modelo. Requieren haber corrido run_pipeline.sh al menos una vez."""
import json

import joblib
import numpy as np
import onnxruntime as ort
import pandas as pd
import pytest

import hazards
import monitor
import retrain
import simulate
from config import DATA_PROCESSED, MODELS, REPORTS, TRAIN_END
from features import DENGUE_FEATURES, HORIZON_WEEKS, complete_rows

FEATS = DATA_PROCESSED / "features.parquet"
pytestmark = pytest.mark.skipif(not FEATS.exists(), reason="corre ml/run_pipeline.sh primero")


@pytest.fixture(scope="module")
def feats():
    return pd.read_parquet(FEATS)


# ---------- datos ----------
def test_historia_simulada_estable_al_agregar_semanas():
    """Reentrenar cada semana no puede reescribir el pasado: cada distrito tiene su propio flujo aleatorio."""
    df = simulate.climate_table()
    ids = sorted(df.district_id.unique())[:3]
    full = df[df.district_id.isin(ids)].reset_index(drop=True)
    keep = full.groupby("district_id").cumcount(ascending=False) >= 30  # quita las 30 semanas finales
    short = full[keep].reset_index(drop=True)
    a, b = simulate.simulate_dengue(full), simulate.simulate_dengue(short)
    sa, sb = simulate.simulate_simple(full), simulate.simulate_simple(short)
    for did in ids:
        i_full, i_short = np.where(full.district_id == did)[0], np.where(short.district_id == did)[0]
        n = len(i_short)
        assert (a[i_full][:n] == b[i_short]).all(), did
        for k in sa:
            assert (sa[k][i_full][:n] == sb[k][i_short]).all(), (did, k)


def test_objetivo_alineado_sin_fuga_de_datos(feats):
    """dengue_next(t) debe ser la suma de los casos de t+1..t+4: nada de t o anterior."""
    d = feats[feats.district_id == "piu-piura"].sort_values("week").reset_index(drop=True)
    k = 100
    esperado = d.dengue.iloc[k + 1:k + 1 + HORIZON_WEEKS].sum()
    assert d.dengue_next.iloc[k] == esperado


def test_variables_sin_nulos_en_filas_completas(feats):
    rows = complete_rows(feats)
    assert len(rows) > 20000
    assert not rows[DENGUE_FEATURES].isna().any().any()


def test_canal_endemico_usa_solo_entrenamiento(feats):
    ch = pd.read_parquet(DATA_PROCESSED / "endemic_channel.parquet")
    assert ch.canal.notna().all() and (ch.canal >= 0).all()
    assert feats.week.max() > pd.Timestamp(TRAIN_END)  # hay datos posteriores que no entraron al canal


# ---------- modelos ----------
@pytest.mark.parametrize("prefix,bundle", [("", "dengue.joblib"), ("prod_", "dengue_prod.joblib")])
def test_onnx_coincide_con_sklearn(feats, prefix, bundle):
    b = joblib.load(MODELS / bundle)
    X = complete_rows(feats)[DENGUE_FEATURES].tail(200).values.astype(np.float32)
    sess = ort.InferenceSession(str(MODELS / f"{prefix}dengue_outbreak.onnx"))
    got = sess.run(None, {"features": X})[1][:, 1]
    assert np.abs(got - b["clf"].predict_proba(X)[:, 1]).max() < 1e-4
    for q in ("p10", "p50", "p90"):
        s = ort.InferenceSession(str(MODELS / f"{prefix}dengue_cases_{q}.onnx"))
        out = s.run(None, {"features": X})[0].ravel()
        assert np.abs(out - b["regs"][q].predict(X)).max() < 1e-3


def test_probabilidades_y_rangos_validos(feats):
    b = joblib.load(MODELS / "dengue_prod.joblib")
    X = complete_rows(feats)[DENGUE_FEATURES].tail(500).values
    p = b["clf"].predict_proba(X)[:, 1]
    assert ((p >= 0) & (p <= 1)).all()


def test_metricas_superan_la_linea_base():
    m = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))["dengue"]
    assert m["modelo"]["auc"] > m["linea_base_canal_endemico"]["auc"]
    assert m["casos"]["mae_modelo_p50"] < m["casos"]["mae_linea_base_ultimas_4_semanas"]
    assert 0.7 < m["casos"]["cobertura_p10_p90"] <= 1.0  # el rango dice ~80%: no debe ser ridículo ni vacío


# ---------- lluvias extremas ----------
def test_umbrales_de_lluvia_ordenados_y_eventos_en_anios_nino():
    daily = hazards.load_daily()
    th = hazards.thresholds(daily)
    assert all(t["alto"] > t["medio"] > 0 for t in th.values())
    por_anio = hazards.backtest(daily, th)
    normales = [por_anio[y] for y in (2018, 2020, 2022, 2024)]
    assert por_anio[2017] > 10 * (np.mean(normales) + 1)  # Niño costero 2017
    assert por_anio[2023] > 10 * (np.mean(normales) + 1)  # 2023 no se usó para fijar los umbrales


# ---------- monitoreo y reentrenamiento ----------
def test_psi_detecta_deriva():
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 5000)
    assert monitor.psi(base, rng.normal(0, 1, 2000)) < 0.1
    assert monitor.psi(base, rng.normal(2, 1, 2000)) > 0.25
    assert monitor.psi(base, rng.normal(10, 1, 2000)) > 1  # totalmente fuera de rango


def test_regla_de_promocion():
    campeon = {"brier": 0.05, "auc": 0.97}
    assert retrain.decide(campeon, {"brier": 0.03, "auc": 0.98})[0] is True
    assert retrain.decide(campeon, {"brier": 0.049, "auc": 0.98})[0] is False   # mejora < 5%
    assert retrain.decide(campeon, {"brier": 0.03, "auc": 0.95})[0] is False    # pierde demasiado AUC


def test_reportes_de_monitoreo_completos():
    mon = json.loads((REPORTS / "monitoring.json").read_text(encoding="utf-8"))
    assert mon["estado"] in {"estable", "vigilar", "reentrenar"}
    assert mon["deriva_variables"] and mon["desempeno_por_trimestre"]
    rt = json.loads((REPORTS / "retrain.json").read_text(encoding="utf-8"))
    assert rt["decision"] in {"promovido", "se mantiene el campeón"}
    assert (MODELS / "dengue_prod.joblib").exists()
