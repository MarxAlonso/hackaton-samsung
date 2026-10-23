# Alerta Salud Niño

Alertas tempranas de **dengue** y enfermedades asociadas a **El Niño costero** (leptospirosis, diarreas, golpe de calor e infecciones respiratorias) para 47 distritos de Tumbes, Piura y Lambayeque. Predice con hasta **4 semanas** de anticipación, entrega un **valor de confianza**, avisa de **lluvias extremas** (inundación y huaico) y propone **dónde poner las brigadas** de control para evitar más casos.

Hackathon ISIL 2026 · Sitio publicado: https://alerta-salud-nino.marxchip99.workers.dev

| Para quién | Qué ve |
|---|---|
| **Autoridad de salud** (DIRESA, jefe de establecimiento) | Distritos priorizados por probabilidad de brote, casos esperados con rango, recursos sugeridos, mapa de dengue y de lluvias extremas, mapa de calor, comparación de temporadas y distritos, simulador "¿y si llueve como en 2023?", lectura de cada gráfico con IA e informe PDF. |
| **Plan de acción** (gestión) | Con N brigadas disponibles, ¿en qué distritos evitan más casos? Compara el reparto óptimo con repartir parejo o por probabilidad, con rango de incertidumbre y supuestos editables (efectividad, capacidad, costos). |
| **Ciudadano** | Semáforo de su distrito (considera enfermedades y lluvias extremas), sus riesgos principales, acciones simples, señales de alarma, asistente de prevención con IA e informe PDF. |

## Arquitectura

```
ml/ (Python: solo entrena y exporta)
  ingest.py    → clima real (Open-Meteo) + El Niño (NOAA); descarga incremental (solo días nuevos)
  simulate.py  → casos semanales simulados a partir del clima real (historia estable entre corridas)
  features.py  → variables y objetivos (sin fuga de datos), canal endémico
  train.py     → GradientBoosting (brote) + cuantiles P10/P50/P90 (casos) + logística (otras 4)
  monitor.py   → deriva de datos (PSI), desempeño por trimestre, decisión de reentrenar
  retrain.py   → campeón vs retador sobre semanas que ninguno vio; promueve solo si mejora
  hazards.py   → índice de lluvias extremas (percentiles históricos de cada distrito)
  export.py    → web/public/data/*.json + modelos .onnx + api/models/

web/ (Astro 7 en Cloudflare Workers)
  /            inicio · /ciudadano · /autoridad · /plan · /modelo · /reporte (PDF)
  /api/explicar  Workers AI (Llama 3.3 70B): explica distritos, gráficos, plan e informe; texto de respaldo si falla

api/ (FastAPI + Docker)
  GET /health · /distritos · /metricas · /monitoreo   POST /predict · /predict/batch · /optimize
```

El modelo de **producción** (el retador promovido) predice "hoy"; los replays de 2017 y 2023 usan el **campeón de evaluación**, entrenado solo con 2015–2021, que nunca vio esas epidemias.

## Resultados (prueba 2022–2026, periodo que el modelo de evaluación nunca vio)

| Métrica | Modelo | Línea base |
|---|---|---|
| AUC brote de dengue (4 semanas) | 0,984 | 0,790 (canal endémico) |
| Recall (brotes anticipados) | 69% | 59% |
| AUC en temporada con casos activos | 0,932 | — |
| PR-AUC anticipando un brote **nuevo** | 0,62 | 0,017 (azar) |
| Error en casos (MAE, 4 semanas) | 12,6 | 27,1 (repetir últimas 4 semanas) |
| Casos reales dentro del rango P10–P90 | 95% | — |

El AUC global se infla con semanas fáciles; la métrica exigente es anticipar un brote nuevo. Detalle en [`ml/reports/model_card.md`](ml/reports/model_card.md).

**Monitoreo y reentrenamiento (hoy):** el mar Niño 1+2 está en +5,3 °C, fuera del rango de entrenamiento (máx. 2,7 °C). El monitoreo lo detecta (PSI 7,3; Brier reciente 0,053 vs 0,022), el retador mejora el Brier 32% en las últimas 26 semanas y se promueve a producción.

**Lluvias extremas:** los días-distrito sobre el umbral extremo fueron 112 en 2017 y 45 en 2023 (año no usado para fijar los umbrales) frente a ~0 en años normales.

## Cómo correrlo

### 1. Pipeline de datos y modelo (Python 3.12+)

```bash
cd ml
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux/Mac: .venv/bin/python
bash run_pipeline.sh          # ingesta → simulación → entrenamiento → monitoreo → reentrenamiento → exportación
python -m pytest tests -q     # 12 pruebas del pipeline
mlflow ui --backend-store-uri sqlite:///mlflow.db   # experimentos (también en reports/experiments.jsonl)
```

La API gratuita de Open-Meteo tiene límite por hora. La ingesta es **incremental** (la primera vez descarga toda la historia; después solo los días nuevos) y se reanuda sola si se corta.

### 2. Sitio web (Node 22+)

```bash
cd web
npm install
npm run dev        # http://localhost:4321
npm run build && npx wrangler deploy   # publica en Cloudflare (requiere `npx wrangler login`)
```

Workers AI necesita una cuenta de Cloudflare (tiene capa gratuita). Sin ella, `/api/explicar` responde con una explicación armada con plantilla y la demo sigue funcionando. Ojo: Wrangler guarda el ID de cuenta en `web/node_modules/.cache/wrangler/wrangler-account.json`; revísalo si publicas desde otra cuenta.

### 3. API REST

```bash
cd api
../ml/.venv/Scripts/python -m uvicorn main:app --reload   # http://localhost:8000/docs
../ml/.venv/Scripts/python -m pytest -q                   # 19 pruebas
docker build -t alerta-salud-api . && docker run -p 8000:8000 alerta-salud-api
```

```bash
curl -X POST localhost:8000/predict  -H "content-type: application/json" -d '{"district_id":"piu-castilla","lluvia_pct":100,"temp_delta":1}'
curl -X POST localhost:8000/optimize -H "content-type: application/json" -d '{"escenario":"2023","brigadas":20,"efectividad":0.3,"costo_brigada":10000,"costo_caso":800}'
```

### 4. Reentrenamiento semanal automático

`.github/workflows/retrain.yml` corre cada lunes: ingesta incremental, simulación, entrenamiento, monitoreo, campeón vs retador, tests y, solo si todo pasa, publica el sitio. Necesita los secretos `CLOUDFLARE_API_TOKEN` y `CLOUDFLARE_ACCOUNT_ID` en el repositorio. También se lanza a mano desde la pestaña Actions.

## Datos: qué es real y qué es simulado

- **Real:** clima diario 2015–2026 por distrito (Open-Meteo, reanálisis ERA5), pronóstico de 16 días, anomalía semanal del mar Niño 1+2 e índice ONI (NOAA).
- **Simulado:** casos semanales de las 5 enfermedades, generados con mecanismos epidemiológicos a partir del clima real ([`ml/reports/dataset_card.md`](ml/reports/dataset_card.md)). Por eso los brotes simulados caen en 2017 y 2023. Cada distrito tiene su propio flujo aleatorio, así que agregar semanas nuevas no reescribe el pasado. El CDC-MINSA publica los casos por distrito sobre todo en PDF; conectarlos es el siguiente paso.
- **Supuestos del plan de brigadas** (efectividad 30%, 15 000 habitantes por brigada, costos de ejemplo): editables y a validar con la DIRESA.

## Uso responsable

Es un sistema de **apoyo a la decisión**: no reemplaza la vigilancia epidemiológica ni los comunicados del MINSA y el ENFEN. La IA solo redacta explicaciones con los números del modelo; no diagnostica ni receta. No se usan datos personales.

## Licencia

[MIT](LICENSE). Los casos de enfermedad son simulados; el sistema es de apoyo a la decisión y no reemplaza la vigilancia oficial.
