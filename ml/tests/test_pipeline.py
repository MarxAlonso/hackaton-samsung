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
from features import FEATURES, HORIZON_WEEKS, complete_rows

FEATS = DATA_PROCESSED / "features.parquet"
pytestmark = pytest.mark.skipif(not FEATS.exists(), reason="corre ml/run_pipeline.sh primero")


@pytest.fixture(scope="module")
def feats():
    return pd.read_parquet(FEATS)


# ---------- datos ----------
def test_golpe_de_calor_simulado_es_estable_al_agregar_semanas():
    """Reentrenar cada semana no puede reescribir el pasado: cada distrito tiene su propio flujo aleatorio."""
    df = simulate.climate_table()
    ids = sorted(df.district_id.unique())[:3]
    full = df[df.district_id.isin(ids)].reset_index(drop=True)
    keep = full.groupby("district_id").cumcount(ascending=False) >= 30  # quita las 30 semanas finales
    short = full[keep].reset_index(drop=True)
    a, b = simulate.simulate_heat(full), simulate.simulate_heat(short)
    for did in ids:
        i_full, i_short = np.where(full.district_id == did)[0], np.where(short.district_id == did)[0]
        assert (a[i_full][:len(i_short)] == b[i_short]).all(), did


def test_objetivo_alineado_sin_fuga_de_datos(feats):
    """dengue_next(t) debe ser la suma de los casos de t+1..t+4: nada de t o anterior."""
    d = feats[feats.district_id == "piu-piura"].sort_values("week").reset_index(drop=True)
    k = 100
    assert d.dengue_next.iloc[k] == d.dengue.iloc[k + 1:k + 1 + HORIZON_WEEKS].sum()


def test_casos_desconocidos_no_se_vuelven_ceros(feats):
    """Después del último dato oficial los casos son NaN; los objetivos y las ventanas también (nunca 0)."""
    d = feats[feats.district_id == "tum-tumbes"].sort_values("week")
    last_known = d.dengue.last_valid_index()
    assert d.dengue.iloc[last_known + 1:].isna().all()
    assert d.dengue_next.iloc[last_known - 2:].isna().all()          # a menos de 4 semanas del final falta el futuro
    assert d.dengue_outbreak.iloc[last_known - 2:].isna().all()      # y no se inventa un "no hubo brote"
    assert d.inc_52.iloc[last_known + 1:].isna().all()
    assert feats.dengue_outbreak.dropna().isin([0.0, 1.0]).all()


def test_variables_sin_nulos_en_filas_completas(feats):
    for family, cols in FEATURES.items():
        rows = complete_rows(feats, cols)
        assert len(rows) > 20000, family
        assert not rows[cols].isna().any().any(), family
        assert rows.dengue_outbreak.notna().all() and rows.dengue_next.notna().all()


def test_la_familia_clima_no_usa_casos(feats):
    from features import CASE_FEATURES
    assert not set(FEATURES["clima"]) & set(CASE_FEATURES)
    # y por eso puede predecir hoy, cuando no hay casos recientes
    now = feats.dropna(subset=FEATURES["clima"]).week.max()
    assert now > feats.dropna(subset=FEATURES["casos"]).week.max() + pd.Timedelta(weeks=20)


def test_canal_endemico_usa_solo_entrenamiento(feats):
    ch = pd.read_parquet(DATA_PROCESSED / "endemic_channel.parquet")
    assert ch.canal.notna().all() and (ch.canal >= 0).all()
    assert feats.week.max() > pd.Timestamp(TRAIN_END)  # hay datos posteriores que no entraron al canal


# ---------- modelos ----------
FILES = [("", "dengue.joblib", "casos"), ("clima_", "dengue_clima.joblib", "clima"),
         ("prod_", "dengue_prod.joblib", "casos"), ("prod_clima_", "dengue_clima_prod.joblib", "clima")]


@pytest.mark.parametrize("prefix,bundle,family", FILES)
def test_onnx_coincide_con_sklearn(feats, prefix, bundle, family):
    b = joblib.load(MODELS / bundle)
    X = complete_rows(feats, FEATURES[family])[FEATURES[family]].tail(200).values.astype(np.float32)
    sess = ort.InferenceSession(str(MODELS / f"{prefix}dengue_outbreak.onnx"))
    got = sess.run(None, {"features": X})[1][:, 1]
    assert np.abs(got - b["clf"].predict_proba(X)[:, 1]).max() < 1e-4
    for q in ("p10", "p50", "p90"):
        s = ort.InferenceSession(str(MODELS / f"{prefix}dengue_cases_{q}.onnx"))
        out = s.run(None, {"features": X})[0].ravel()
        assert np.abs(out - b["regs"][q].predict(X)).max() < 1e-3


def test_probabilidades_validas(feats):
    for bundle, family in (("dengue_prod.joblib", "casos"), ("dengue_clima_prod.joblib", "clima")):
        b = joblib.load(MODELS / bundle)
        X = complete_rows(feats, FEATURES[family])[FEATURES[family]].tail(500).values
        p = b["clf"].predict_proba(X)[:, 1]
        assert ((p >= 0) & (p <= 1)).all()


def test_metricas_con_datos_reales():
    m = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))
    casos, clima = m["dengue"], m["dengue_clima"]
    # Con casos recientes gana a la línea base del MINSA y a repetir las últimas 4 semanas
    assert casos["modelo"]["auc"] > casos["linea_base"]["auc"]
    assert casos["casos"]["mae_modelo_p50"] < casos["casos"]["mae_linea_base_ultimas_4_semanas"]
    assert 0.6 < casos["casos"]["cobertura_p10_p90"] <= 1.0
    # Solo clima ordena mejor que el calendario puro (es un modelo modesto, y así se presenta)
    assert clima["modelo"]["auc"] > clima["linea_base"]["auc"]
    assert clima["modelo"]["auc"] < casos["modelo"]["auc"]
    # La evaluación progresiva existe para 2022, 2023 y 2024
    assert [r["anio"] for r in casos["evaluacion_progresiva"]] == [2022, 2023, 2024]
    assert all(r["brier"] < r["brier_sin_informacion"] for r in casos["evaluacion_progresiva"])


def test_los_datos_reales_estan_documentados():
    m = json.loads((REPORTS / "metrics.json").read_text(encoding="utf-8"))
    cov = m["datos"]
    for d in ("dengue", "leptospirosis", "eda", "ira"):
        assert cov[d]["anio_provisional_descartado"] and cov[d]["casos_total"] > 1000
    assert "Simulado" in cov["golpe_calor"]["fuente"]


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
    assert all(d["variable"] not in ("inc_0", "inc_0_3", "inc_52") for d in mon["deriva_variables"])  # solo datos que llegan al día
    rt = json.loads((REPORTS / "retrain.json").read_text(encoding="utf-8"))
    assert rt["decision"] in {"promovido", "se mantiene el campeón"} and rt["familia"] == "clima"
    assert set(rt["familias"]) == {"clima", "casos"}
    for f in ("dengue_prod.joblib", "dengue_clima_prod.joblib"):
        assert (MODELS / f).exists()
