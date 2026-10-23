"""Casos reales del CDC-MINSA: semanas epidemiológicas, cobertura del último año, valores desconocidos y descarga.
Estas pruebas usan archivos pequeños creados al vuelo: no necesitan bajar los 400 MB."""
import json

import numpy as np
import pandas as pd
import pytest

import ingest_cases
import real_cases
from config import districts_frame

D = districts_frame()
PIURA, CASTILLA, TUMBES = "200101", "200104", "240101"   # ubigeo de Piura, Castilla y Tumbes


def test_ubigeos_validos_y_unicos():
    assert D.ubigeo.is_unique and D.ubigeo.str.len().eq(6).all()
    prefijo = {"Tumbes": "24", "Piura": "20", "Lambayeque": "14"}
    assert all(r.ubigeo.startswith(prefijo[r.department]) for r in D.itertuples())
    # los tres cuyo nombre viene dañado en el archivo oficial (Ñ) se cruzan por código
    codes = D.set_index("district_id").ubigeo
    assert codes["piu-parinas"] == "200701" and codes["piu-tambogrande"] == "200114" and codes["lam-ferrenafe"] == "140201"


@pytest.mark.parametrize("year,week,monday", [
    (2023, 1, "2023-01-02"),    # el 1 de enero de 2023 fue domingo: la semana 1 empieza ese día
    (2025, 1, "2024-12-30"),    # la semana 1 de 2025 contiene el 4 de enero: empieza el domingo 29 de diciembre de 2024
    (2024, 52, "2024-12-23"),
    (2025, 53, "2025-12-29"),   # 2025 tiene 53 semanas
    (2026, 1, "2026-01-05"),    # 2026: el 4 de enero es domingo
])
def test_semana_epidemiologica_a_lunes(year, week, monday):
    assert pd.Timestamp(real_cases.epi_week_monday(year, week)[0]) == pd.Timestamp(monday)


def test_las_semanas_siguen_una_a_otra():
    wk = real_cases.epi_week_monday(np.full(52, 2023), np.arange(1, 53))
    assert (np.diff(wk.values).astype("timedelta64[D]").astype(int) == 7).all()


@pytest.fixture
def archivos(tmp_path):
    """Mini versiones de los 5 archivos oficiales, con casos solo en Castilla y Tumbes."""
    (tmp_path / "dengue.csv").write_text(
        "departamento,provincia,distrito,localidad,enfermedad,ano,semana,diagnostic,tipo_dx,diresa,ubigeo,localcod,edad,tipo_edad,sexo\n"
        + "\n".join(["PIURA,PIURA,CASTILLA,X,DENGUE SIN SIGNOS DE ALARMA,2024,10,A97,C,20,200104,,30,A,M"] * 3
                    + ["PIURA,PIURA,CASTILLA,X,DENGUE SIN SIGNOS DE ALARMA,2024,10,A97,P,20,200104,,30,A,M"]
                    + ["PIURA,PIURA,CASTILLA,X,DENGUE SIN SIGNOS DE ALARMA,2024,11,A97,C,20,200104,,30,A,F"]
                    + ["TUMBES,TUMBES,TUMBES,X,DENGUE SIN SIGNOS DE ALARMA,2024,52,A97,C,24,240101,,30,A,F"]
                    + ["PIURA,PIURA,CASTILLA,X,DENGUE SIN SIGNOS DE ALARMA,2025,3,A97,C,20,200104,,30,A,F"]  # semana 3 de 2025: la última del archivo está incompleta y no se usa
                    + ["LIMA,LIMA,LIMA,X,DENGUE SIN SIGNOS DE ALARMA,2024,10,A97,C,15,150101,,30,A,F"]) + "\n",  # fuera del piloto
        encoding="utf-8")
    (tmp_path / "zoonosis.csv").write_text(
        "departamento,provincia,distrito,localidad,enfermedad,ano,semana,diagnostic,tipo_dx,diresa,ubigeo,localcod,edad,tipo_edad,sexo\n"
        "PIURA,PIURA,CASTILLA,X,LEPTOSPIROSIS,2024,10,A27,C,20,200104,,30,A,M\n"
        "PIURA,PIURA,CASTILLA,X,OFIDISMO,2024,10,T63,C,20,200104,,30,A,M\n"
        "PIURA,PIURA,CASTILLA,X,LEPTOSPIROSIS,2025,1,A27,C,20,200104,,30,A,M\n", encoding="utf-8")
    (tmp_path / "eda.csv").write_text(
        "departamento,provincia,distrito,ano,semana,sub_reg_nt,ubigeo,episodios_men5,hospitalizados_men5,defunciones_men5,episodios_may5,hospitalizados_may5,defunciones_may5\n"
        "PIURA,PIURA,CASTILLA,2024,10,20,200104,5,0,0,7,0,0\n"
        "PIURA,PIURA,CASTILLA,2024,10,36,200104,2,0,0,1,0,0\n"   # dos subregiones en la misma semana: se suman
        "PIURA,PIURA,CASTILLA,2025,2,20,200104,9,0,0,9,0,0\n", encoding="utf-8")
    (tmp_path / "ira.csv").write_text(
        "﻿departamento;provincia;distrito;ano;semana;sub_reg_nt;ubigeo;ira_no_neumonia;neumonias_men5;neumonias_60mas;hospitalizados_men5;hospitalizados_60mas;defunciones_men5;defunciones_60mas\n"
        "PIURA;PIURA;CASTILLA;2024;10;20;200104;100;4;2;0;0;0;0\n"
        "PIURA;PIURA;CASTILLA;2025;2;20;200104;50;1;1;0;0;0;0\n", encoding="utf-8")
    (tmp_path / "dengue_piura_gore.csv").write_text(
        "FECHA_CORTE,DEPARTAMENTO,PROVINCIA,DISTRITO,UBIGEO,FECHA_INGRESO,ANO,LOCALIDAD,CENTRO_SALUD,EDAD,TIPO_EDAD,SEXO,FECHA_INICIO_SINTOMAS,FECHA_NOTIFICACION,SEMANA_NOTIFICACION\n"
        + "\n".join(["20260702,PIURA,PIURA,CASTILLA,200104,20260630,2026,X,Y,30,A,Masculino,20260601,20260602,23"] * 4
                    + ["20260702,PIURA,PIURA,CASTILLA,200104,20260630,2026,X,Y,30,A,Masculino,20260630,20260630,26"]) + "\n",  # semana 26 incompleta
        encoding="latin-1")
    return tmp_path


def test_construccion_semanal(archivos):
    weeks = pd.date_range("2023-12-04", "2026-07-06", freq="W-MON")
    table, cov = real_cases.build(weeks, directory=archivos)
    cast = table[table.district_id == "piu-castilla"].set_index("week")
    w10 = real_cases.epi_week_monday(2024, 10)[0]
    # 3 confirmados + 1 probable de la semana 10; el de la semana 11 va aparte
    assert cast.loc[w10, "dengue"] == 4 and cast.loc[real_cases.epi_week_monday(2024, 11)[0], "dengue"] == 1
    assert cast.loc[w10, "eda"] == 15                       # 5+7+2+1 de dos subregiones
    assert cast.loc[w10, "ira"] == 106                      # 100 + 4 + 2
    assert cast.loc[w10, "leptospirosis"] == 1              # el ofidismo no cuenta
    # una semana sin filas dentro del periodo cubierto es CERO...
    assert cast.loc[real_cases.epi_week_monday(2024, 20)[0], "dengue"] == 0
    # ...y después de la cobertura (2025, SE 2: la SE 3 es la última del archivo y está incompleta) es DESCONOCIDA
    fin = real_cases.epi_week_monday(2024, 52)[0]
    assert cast.loc[fin, "dengue"] == 0 and cast.loc[real_cases.epi_week_monday(2025, 2)[0], "dengue"] == 0
    assert pd.isna(cast.loc[real_cases.epi_week_monday(2025, 3)[0], "dengue"])
    tum = table[table.district_id == "tum-tumbes"].set_index("week")
    assert tum.loc[fin, "dengue"] == 1
    # lo que no es del piloto no entra
    assert table.dengue.sum() == 4 + 1 + 1
    assert cov["dengue"]["hasta"] == str(real_cases.epi_week_monday(2025, 2)[0].date()) and cov["dengue"]["ultima_semana_epidemiologica"] == "2025-SE2"


def test_regional_de_piura_queda_aparte_y_sin_semana_incompleta(archivos):
    weeks = pd.date_range("2024-12-02", "2026-07-06", freq="W-MON")
    table, cov = real_cases.build(weeks, directory=archivos)
    cast = table[table.district_id == "piu-castilla"].set_index("week")
    assert cast.loc[real_cases.epi_week_monday(2026, 23)[0], "dengue_gore"] == 4
    # la semana 26 trae el corte del 2 de julio (jueves): está incompleta y no se usa
    assert pd.isna(cast.loc[real_cases.epi_week_monday(2026, 26)[0], "dengue_gore"])
    assert cast.dengue_gore.dropna().index.min() >= pd.Timestamp("2025-01-01")
    # y NO se mezcla con la serie nacional que usa el modelo
    assert pd.isna(cast.loc[real_cases.epi_week_monday(2026, 23)[0], "dengue"])
    assert table[table.district_id == "tum-tumbes"].dengue_gore.isna().all()  # solo existe para Piura


def test_cuando_el_archivo_incluye_un_anio_nuevo_el_anterior_sigue_usandose(archivos):
    """El año anterior no se descarta: solo la última semana del año en curso queda fuera por incompleta."""
    p = archivos / "dengue.csv"
    p.write_text(p.read_text(encoding="utf-8") + "PIURA,PIURA,CASTILLA,X,DENGUE SIN SIGNOS DE ALARMA,2026,2,A97,C,20,200104,,30,A,F\n", encoding="utf-8")
    weeks = pd.date_range("2023-12-04", "2026-07-06", freq="W-MON")
    table, cov = real_cases.build(weeks, directory=archivos)
    cast = table[table.district_id == "piu-castilla"].set_index("week")
    assert cov["dengue"]["ultima_semana_epidemiologica"] == "2026-SE1"
    assert cast.loc[real_cases.epi_week_monday(2025, 3)[0], "dengue"] == 1   # 2025 cuenta entero
    assert pd.isna(cast.loc[real_cases.epi_week_monday(2026, 2)[0], "dengue"])


def test_un_anio_cerrado_se_usa_hasta_su_ultima_semana(archivos):
    p = archivos / "dengue.csv"
    p.write_text(p.read_text(encoding="utf-8") + "PIURA,PIURA,CASTILLA,X,DENGUE SIN SIGNOS DE ALARMA,2025,53,A97,C,20,200104,,30,A,F\n", encoding="utf-8")
    weeks = pd.date_range("2025-12-01", "2026-02-02", freq="W-MON")
    table, cov = real_cases.build(weeks, directory=archivos)
    cast = table[table.district_id == "piu-castilla"].set_index("week")
    assert cov["dengue"]["ultima_semana_epidemiologica"] == "2025-SE53"
    assert cast.loc[real_cases.epi_week_monday(2025, 53)[0], "dengue"] == 1   # la SE 53 de un año cerrado cuenta
    assert cast.loc[real_cases.epi_week_monday(2025, 52)[0], "dengue"] == 0


# ---------- descarga ----------
def test_descarga_solo_si_cambio(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_cases, "MINSA_DIR", tmp_path)
    monkeypatch.setattr(ingest_cases, "SOURCES", {"demo": ("/dataset/x", "demo.csv")})
    estado = {"bytes": 5, "modificado": "lunes", "llamadas": 0}
    monkeypatch.setattr(ingest_cases, "discover_url", lambda page, fallback: "https://x/demo.csv")
    monkeypatch.setattr(ingest_cases, "remote_info", lambda url: {"url": url, "bytes": estado["bytes"], "modificado": estado["modificado"]})

    def fake_download(url, target):
        estado["llamadas"] += 1
        target.write_bytes(b"x" * estado["bytes"])
    monkeypatch.setattr(ingest_cases, "download", fake_download)

    assert ingest_cases.sync()["demo"]["estado"] == "descargado" and estado["llamadas"] == 1
    assert ingest_cases.sync()["demo"]["estado"] == "al día" and estado["llamadas"] == 1      # no vuelve a bajar
    estado.update(bytes=8, modificado="martes")                                                # el portal publicó una versión nueva
    assert ingest_cases.sync()["demo"]["estado"] == "descargado" and estado["llamadas"] == 2
    assert (tmp_path / "demo.csv").stat().st_size == 8
    assert json.loads((tmp_path / "demo.meta.json").read_text())["modificado"] == "martes"


def test_descarga_incompleta_se_rechaza(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_cases, "MINSA_DIR", tmp_path)
    monkeypatch.setattr(ingest_cases, "SOURCES", {"demo": ("/dataset/x", "demo.csv")})
    monkeypatch.setattr(ingest_cases, "discover_url", lambda page, fallback: "https://x/demo.csv")
    monkeypatch.setattr(ingest_cases, "remote_info", lambda url: {"url": url, "bytes": 100, "modificado": "hoy"})
    monkeypatch.setattr(ingest_cases, "download", lambda url, target: target.write_bytes(b"corto"))
    with pytest.raises(RuntimeError, match="incompleta"):
        ingest_cases.sync()


def test_descubre_el_enlace_vigente(monkeypatch):
    class Respuesta:
        text = '<a href="https://www.datosabiertos.gob.pe/sites/default/files/datos_abiertos_vigilancia_dengue_2000_2026_0.csv">Descargar</a>'
        def raise_for_status(self): pass
    monkeypatch.setattr(ingest_cases.requests, "get", lambda *a, **k: Respuesta())
    assert ingest_cases.discover_url("/dataset/x", "viejo.csv").endswith("dengue_2000_2026_0.csv")   # el nombre cambia cada año


# ---------- contra los archivos oficiales (solo si están descargados) ----------
OFICIAL = real_cases.MINSA / "dengue.csv"


@pytest.mark.skipif(not OFICIAL.exists(), reason="descarga primero con ingest_cases.py")
def test_la_tabla_semanal_conserva_los_casos_del_archivo_oficial():
    cases = pd.read_parquet(real_cases.DATA_PROCESSED / "cases_weekly.parquet")
    raw = pd.read_csv(OFICIAL, dtype={"ubigeo": str}, usecols=["ubigeo", "ano", "tipo_dx"])
    raw = raw[raw.tipo_dx.isin(["C", "P"]) & raw.ubigeo.isin(D.ubigeo) & raw.ano.between(2016, 2024)]
    ours = cases[cases.week.between("2016-01-04", "2024-12-23")].dengue.sum()
    assert abs(ours - len(raw)) / len(raw) < 0.002    # las semanas 1 de enero que caen en el año vecino explican la diferencia
    assert cases[cases.week.dt.year == 2024].dengue.sum() > 30000          # 2024: epidemia real
    assert cases[cases.week.dt.year.isin([2018, 2019])].dengue.sum() < 5000  # años tranquilos
