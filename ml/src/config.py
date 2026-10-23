"""Configuración compartida del pipeline: rutas, fechas y distritos del norte del Perú.

Población y acceso a agua son aproximaciones (orden de magnitud INEI 2017) usadas solo
para la simulación del hackathon. Coordenadas y altitud: centroides aproximados.
"""
import sys
from pathlib import Path

# La consola de Windows usa cp1252 por defecto; forzamos UTF-8 para tildes y símbolos
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
WEB_DATA = ROOT.parent / "web" / "public" / "data"
API_MODELS = ROOT.parent / "api" / "models"

START_DATE = "2015-01-01"
TRAIN_END = "2021-12-31"  # entrenamiento <= 2021, prueba 2022+ (incluye la epidemia 2023)
HORIZON_WEEKS = 4
SEED = 42

DISEASES = {
    "dengue": "Dengue",
    "leptospirosis": "Leptospirosis",
    "eda": "Diarreas (EDA)",
    "golpe_calor": "Golpe de calor",
    "ira": "Infecciones respiratorias (IRA)",
}

# id, distrito, provincia, departamento, lat, lon, altitud (m), población, % hogares con agua por red
DISTRICTS = [
    ("tum-tumbes", "Tumbes", "Tumbes", "Tumbes", -3.566, -80.451, 7, 111000, 0.78),
    ("tum-corrales", "Corrales", "Tumbes", "Tumbes", -3.601, -80.481, 15, 25000, 0.70),
    ("tum-lacruz", "La Cruz", "Tumbes", "Tumbes", -3.638, -80.588, 5, 9500, 0.66),
    ("tum-sanjacinto", "San Jacinto", "Tumbes", "Tumbes", -3.643, -80.452, 30, 9000, 0.55),
    ("tum-pampas", "Pampas de Hospital", "Tumbes", "Tumbes", -3.694, -80.437, 40, 7200, 0.52),
    ("tum-zarumilla", "Zarumilla", "Zarumilla", "Tumbes", -3.502, -80.276, 10, 23000, 0.68),
    ("tum-aguasverdes", "Aguas Verdes", "Zarumilla", "Tumbes", -3.481, -80.245, 10, 25000, 0.60),
    ("tum-papayal", "Papayal", "Zarumilla", "Tumbes", -3.571, -80.229, 25, 5500, 0.50),
    ("tum-zorritos", "Zorritos", "Contralmirante Villar", "Tumbes", -3.680, -80.678, 10, 12500, 0.62),
    ("tum-puntasal", "Canoas de Punta Sal", "Contralmirante Villar", "Tumbes", -3.947, -80.940, 10, 6000, 0.55),
    ("piu-piura", "Piura", "Piura", "Piura", -5.194, -80.632, 30, 160000, 0.88),
    ("piu-castilla", "Castilla", "Piura", "Piura", -5.196, -80.610, 30, 160000, 0.80),
    ("piu-26oct", "Veintiséis de Octubre", "Piura", "Piura", -5.180, -80.670, 35, 165000, 0.76),
    ("piu-catacaos", "Catacaos", "Piura", "Piura", -5.265, -80.675, 25, 75000, 0.62),
    ("piu-curamori", "Cura Mori", "Piura", "Piura", -5.320, -80.660, 20, 19500, 0.55),
    ("piu-laarena", "La Arena", "Piura", "Piura", -5.345, -80.712, 20, 38000, 0.58),
    ("piu-launion", "La Unión", "Piura", "Piura", -5.401, -80.741, 15, 41000, 0.60),
    ("piu-tallan", "El Tallán", "Piura", "Piura", -5.405, -80.683, 15, 5000, 0.45),
    ("piu-sullana", "Sullana", "Sullana", "Piura", -4.904, -80.685, 60, 180000, 0.82),
    ("piu-bellavista", "Bellavista", "Sullana", "Piura", -4.890, -80.677, 60, 38000, 0.72),
    ("piu-escudero", "Ignacio Escudero", "Sullana", "Piura", -4.846, -80.870, 50, 20000, 0.55),
    ("piu-marcavelica", "Marcavelica", "Sullana", "Piura", -4.878, -80.705, 60, 29000, 0.60),
    ("piu-querecotillo", "Querecotillo", "Sullana", "Piura", -4.838, -80.647, 80, 25500, 0.58),
    ("piu-paita", "Paita", "Paita", "Piura", -5.085, -81.114, 10, 90000, 0.70),
    ("piu-parinas", "Pariñas (Talara)", "Talara", "Piura", -4.580, -81.270, 15, 90000, 0.85),
    ("piu-mancora", "Máncora", "Talara", "Piura", -4.106, -81.047, 10, 13000, 0.58),
    ("piu-chulucanas", "Chulucanas", "Morropón", "Piura", -5.093, -80.163, 95, 76000, 0.65),
    ("piu-morropon", "Morropón", "Morropón", "Piura", -5.187, -79.971, 130, 14000, 0.55),
    ("piu-tambogrande", "Tambogrande", "Piura", "Piura", -4.927, -80.344, 70, 120000, 0.48),
    ("piu-laslomas", "Las Lomas", "Piura", "Piura", -4.653, -80.243, 260, 27000, 0.45),
    ("piu-sechura", "Sechura", "Sechura", "Piura", -5.557, -80.822, 10, 45000, 0.66),
    ("piu-ayabaca", "Ayabaca", "Ayabaca", "Piura", -4.639, -79.714, 2715, 38000, 0.40),
    ("piu-huancabamba", "Huancabamba", "Huancabamba", "Piura", -5.238, -79.451, 1930, 30000, 0.45),
    ("lam-chiclayo", "Chiclayo", "Chiclayo", "Lambayeque", -6.771, -79.841, 30, 290000, 0.90),
    ("lam-jlo", "José Leonardo Ortiz", "Chiclayo", "Lambayeque", -6.750, -79.838, 30, 195000, 0.80),
    ("lam-lavictoria", "La Victoria", "Chiclayo", "Lambayeque", -6.790, -79.840, 30, 92000, 0.84),
    ("lam-pimentel", "Pimentel", "Chiclayo", "Lambayeque", -6.836, -79.934, 5, 45000, 0.72),
    ("lam-tuman", "Tumán", "Chiclayo", "Lambayeque", -6.749, -79.700, 70, 30000, 0.62),
    ("lam-patapo", "Pátapo", "Chiclayo", "Lambayeque", -6.738, -79.650, 90, 23000, 0.55),
    ("lam-lambayeque", "Lambayeque", "Lambayeque", "Lambayeque", -6.701, -79.906, 20, 80000, 0.78),
    ("lam-morrope", "Mórrope", "Lambayeque", "Lambayeque", -6.540, -80.011, 15, 47000, 0.42),
    ("lam-tucume", "Túcume", "Lambayeque", "Lambayeque", -6.510, -79.850, 40, 23000, 0.50),
    ("lam-illimo", "Íllimo", "Lambayeque", "Lambayeque", -6.470, -79.854, 45, 9500, 0.52),
    ("lam-jayanca", "Jayanca", "Lambayeque", "Lambayeque", -6.390, -79.822, 60, 18000, 0.50),
    ("lam-motupe", "Motupe", "Lambayeque", "Lambayeque", -6.152, -79.714, 130, 27000, 0.55),
    ("lam-olmos", "Olmos", "Lambayeque", "Lambayeque", -5.985, -79.746, 175, 41000, 0.45),
    ("lam-ferrenafe", "Ferreñafe", "Ferreñafe", "Lambayeque", -6.639, -79.789, 45, 36000, 0.72),
]

DISTRICT_COLUMNS = ["district_id", "district", "province", "department", "lat", "lon",
                    "altitude", "population", "water_access"]


def districts_frame():
    import pandas as pd
    return pd.DataFrame(DISTRICTS, columns=DISTRICT_COLUMNS)
