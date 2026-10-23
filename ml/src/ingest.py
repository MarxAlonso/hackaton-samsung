"""Paso 1 — Ingesta de datos reales vía API.

- Clima diario por distrito: Open-Meteo Archive API (reanálisis ERA5, sin API key).
- Pronóstico 16 días: Open-Meteo Forecast API (solo para mostrar en la interfaz).
- Niño 1+2 semanal (El Niño costero) y ONI mensual: NOAA CPC.

Salida: data/processed/climate_weekly.parquet, enso_weekly.parquet, forecast_daily.parquet
"""
import io
import re
import time
from datetime import date, timedelta

import pandas as pd
import requests

from config import DATA_PROCESSED, DATA_RAW, START_DATE, districts_frame

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
NINO12_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
DAILY_VARS = ["temperature_2m_max", "temperature_2m_mean", "precipitation_sum",
              "relative_humidity_2m_mean"]
BATCH = 6
GRID = 0.25


def _get(url, params=None, retries=6):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.status_code == 429:  # límite por minuto de Open-Meteo
                time.sleep(65)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"No se pudo descargar {url}")


def _daily_frames(payload, ids):
    payload = payload if isinstance(payload, list) else [payload]
    frames = []
    for district_id, loc in zip(ids, payload):
        df = pd.DataFrame(loc["daily"])
        df["district_id"] = district_id
        frames.append(df)
    return frames


def with_grid_cell(districts):
    """ERA5 tiene resolución de 0,25°: distritos vecinos comparten celda y se descargan una vez."""
    districts = districts.copy()
    districts["cell_lat"] = (districts.lat / GRID).round() * GRID
    districts["cell_lon"] = (districts.lon / GRID).round() * GRID
    districts["cell"] = districts.cell_lat.map("{:.2f}".format) + "_" + districts.cell_lon.map("{:.2f}".format)
    return districts


OVERLAP_DAYS = 10  # se vuelven a pedir los últimos días: ERA5 corrige valores recientes


def fetch_climate_daily(end_date):
    """Descarga incremental: si ya hay historia, solo se piden los días nuevos (y un solapamiento)."""
    districts = with_grid_cell(districts_frame())
    cells = districts.drop_duplicates("cell")[["cell", "cell_lat", "cell_lon"]].reset_index(drop=True)
    master = DATA_RAW / "climate_by_cell.parquet"
    history = pd.read_parquet(master) if master.exists() else None
    start = START_DATE
    if history is not None and set(cells.cell) <= set(history.cell):
        start = (pd.to_datetime(history.time).max() - pd.Timedelta(days=OVERLAP_DAYS)).strftime("%Y-%m-%d")
        if start >= end_date:
            print("  Clima al día: no hay días nuevos.")
        else:
            print(f"  Modo incremental: solo desde {start}")
    else:
        history = None  # primera descarga o cambió la lista de distritos
    frames = []
    for i in range(0, len(cells), BATCH):
        chunk = cells.iloc[i:i + BATCH]
        cache = DATA_RAW / f"climate_{start}_{end_date}_cells{i:02d}.parquet"
        if cache.exists():  # permite reanudar si la API corta por límite de uso
            frames.append(pd.read_parquet(cache))
            continue
        if start >= end_date:
            continue
        params = {
            "latitude": ",".join(f"{v:.2f}" for v in chunk.cell_lat),
            "longitude": ",".join(f"{v:.2f}" for v in chunk.cell_lon),
            "start_date": start,
            "end_date": end_date,
            "daily": ",".join(DAILY_VARS),
            "timezone": "America/Lima",
        }
        print(f"  Open-Meteo archivo: celdas {i + 1}-{i + len(chunk)} de {len(cells)}")
        part = pd.concat(_daily_frames(_get(ARCHIVE_URL, params).json(), list(chunk.cell)))
        part = part.rename(columns={"district_id": "cell"})
        part.to_parquet(cache, index=False)
        frames.append(part)
        time.sleep(15)
    new = pd.concat(frames, ignore_index=True) if frames else None
    parts = [x for x in (history, new) if x is not None]
    by_cell = pd.concat(parts, ignore_index=True)
    by_cell["time"] = pd.to_datetime(by_cell["time"])
    # los datos nuevos reemplazan a los viejos en el solapamiento
    by_cell = by_cell.drop_duplicates(["cell", "time"], keep="last").sort_values(["cell", "time"])
    by_cell.to_parquet(master, index=False)
    for stale in DATA_RAW.glob("climate_20*_cells*.parquet"):
        stale.unlink()  # los bloques ya quedaron integrados en el maestro
    daily = districts[["district_id", "cell"]].merge(by_cell, on="cell").drop(columns="cell")
    daily["time"] = pd.to_datetime(daily["time"])
    return daily


def fetch_forecast_daily():
    districts = with_grid_cell(districts_frame())
    cells = districts.drop_duplicates("cell")
    frames = []
    for i in range(0, len(cells), BATCH):
        chunk = cells.iloc[i:i + BATCH]
        params = {
            "latitude": ",".join(f"{v:.2f}" for v in chunk.cell_lat),
            "longitude": ",".join(f"{v:.2f}" for v in chunk.cell_lon),
            "daily": "temperature_2m_max,precipitation_sum",
            "forecast_days": 16,
            "timezone": "America/Lima",
        }
        frames += _daily_frames(_get(FORECAST_URL, params).json(), list(chunk.cell))
    by_cell = pd.concat(frames).rename(columns={"district_id": "cell"})
    forecast = districts[["district_id", "cell"]].merge(by_cell, on="cell").drop(columns="cell")
    forecast["time"] = pd.to_datetime(forecast["time"])
    return forecast


def to_weekly(daily):
    """Agrega a semanas que empiezan el lunes (semana epidemiológica aproximada)."""
    weekly = (
        daily.set_index("time")
        .groupby("district_id")
        .resample("W-MON", label="left", closed="left")
        .agg({
            "precipitation_sum": "sum",
            "temperature_2m_max": "max",
            "temperature_2m_mean": "mean",
            "relative_humidity_2m_mean": "mean",
        })
        .rename(columns={
            "precipitation_sum": "rain_mm",
            "temperature_2m_max": "tmax",
            "temperature_2m_mean": "tmean",
            "relative_humidity_2m_mean": "humidity",
        })
        .reset_index()
        .rename(columns={"time": "week"})
    )
    return weekly


def fetch_nino12():
    text = _get(NINO12_URL).text
    (DATA_RAW / "nino12_weekly.txt").write_text(text, encoding="utf-8")
    rows = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d{2}[A-Z]{3}\d{4})\s+(.*)", line)
        if not m:
            continue
        nums = re.findall(r"-?\d+\.\d", m.group(2))
        if len(nums) >= 2:
            rows.append({"date": pd.to_datetime(m.group(1), format="%d%b%Y"),
                         "nino12_sst": float(nums[0]), "nino12_anom": float(nums[1])})
    return pd.DataFrame(rows)


SEASON_MONTH = {s: i + 1 for i, s in enumerate(
    ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"])}


def fetch_oni():
    text = _get(ONI_URL).text
    (DATA_RAW / "oni.txt").write_text(text, encoding="utf-8")
    oni = pd.read_csv(io.StringIO(text), sep=r"\s+")
    oni["month"] = oni["SEAS"].map(SEASON_MONTH)
    oni["period"] = pd.PeriodIndex.from_fields(year=oni["YR"], month=oni["month"], freq="M")
    return oni[["period", "ANOM"]].rename(columns={"ANOM": "oni"})


def build_enso_weekly(weeks):
    nino = fetch_nino12().sort_values("date")
    oni = fetch_oni()
    enso = pd.DataFrame({"week": sorted(weeks.unique())})
    enso = pd.merge_asof(enso, nino, left_on="week", right_on="date", direction="backward")
    enso["period"] = enso["week"].dt.to_period("M")
    enso = enso.merge(oni, on="period", how="left")
    enso["oni"] = enso["oni"].ffill()
    return enso[["week", "nino12_anom", "oni"]]


def main():
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    end_date = (date.today() - timedelta(days=6)).isoformat()
    print(f"Descargando clima {START_DATE} → {end_date}")
    daily = fetch_climate_daily(end_date)
    daily.to_parquet(DATA_RAW / "climate_daily.parquet", index=False)

    weekly = to_weekly(daily)
    # Se descarta la última semana si está incompleta
    last_full = pd.Timestamp(end_date) - pd.Timedelta(days=6)
    weekly = weekly[weekly["week"] <= last_full]
    weekly.to_parquet(DATA_PROCESSED / "climate_weekly.parquet", index=False)
    print(f"  clima semanal: {len(weekly):,} filas, última semana {weekly.week.max().date()}")

    print("Descargando índices El Niño (NOAA)")
    enso = build_enso_weekly(weekly["week"])
    enso.to_parquet(DATA_PROCESSED / "enso_weekly.parquet", index=False)
    print(f"  Niño 1+2 más reciente: {enso.nino12_anom.iloc[-1]:+.1f} °C | ONI {enso.oni.iloc[-1]:+.2f}")

    print("Descargando pronóstico 16 días")
    try:
        fetch_forecast_daily().to_parquet(DATA_PROCESSED / "forecast_daily.parquet", index=False)
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        # El pronóstico solo se muestra en la interfaz; no detiene el pipeline
        print(f"  Pronóstico no disponible ({exc}); se continúa sin él.")
    print("Ingesta completa.")


if __name__ == "__main__":
    main()
