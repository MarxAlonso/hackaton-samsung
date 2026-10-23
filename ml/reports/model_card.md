# Model card: Alerta Salud Niño

## Propósito
Anticipar, con 4 semanas de anticipación, brotes de dengue y semanas de riesgo alto de leptospirosis, EDA, golpe de calor e IRA en 47 distritos del norte del Perú; avisar de lluvias extremas; y proponer dónde poner las brigadas de control. Sirve para priorizar fumigación, abastecimiento y comunicación de riesgo.

**Usuarios:** DIRESA y jefes de establecimientos de salud (panel de priorización y plan de acción) y ciudadanos (semáforo y prevención).
**Fuera de alcance:** diagnóstico individual, decisiones clínicas y zonas fuera del piloto.

## Modelos

| Salida | Algoritmo | Objetivo |
|---|---|---|
| Probabilidad de brote de dengue | `GradientBoostingClassifier` (250 árboles, profundidad 3) | Alguna de las próximas 4 semanas supera el canal endémico (percentil 75 histórico de la semana del año) con ≥ 5 casos |
| Casos de dengue P10 / P50 / P90 | `GradientBoostingRegressor` sobre log(1+casos): cuantílico para P10/P90 y cuadrático para P50 | Casos totales de las próximas 4 semanas |
| Leptospirosis, EDA, golpe de calor, IRA | Regresión logística estandarizada | Casos de 4 semanas sobre el percentil 80 del distrito |
| Lluvias extremas | **Índice de umbrales** (no entrenado) | Lluvia acumulada en 3 días frente al percentil 99 (intensa) y 99,9 (extrema) de cada distrito, calculados con 2015–2021 |
| Plan de brigadas | **Optimización** (reparto por mayor beneficio por brigada; óptimo exacto, verificado contra programación dinámica) | Casos evitados con N brigadas, efectividad y capacidad por brigada editables |

**Valor de confianza** que se muestra al usuario:
1. La probabilidad de brote. El diagrama de confiabilidad muestra que está bien calibrada.
2. El rango P10–P90 de casos.
3. Una etiqueta de confianza alta, media o baja, que combina la certeza de la probabilidad y el ancho del rango.

**Variables del dengue (17):**
- Lluvia acumulada en 0–1, 2–6 y 7–12 semanas atrás.
- Temperatura media y máxima, y humedad.
- Anomalía Niño 1+2 y ONI.
- Incidencia de esta semana, de las últimas 4 semanas y de las últimas 52 (inmunidad).
- Umbral del canal endémico.
- Altitud, acceso a agua por red, población y época del año.

## Evaluación
Validación temporal: el **campeón de evaluación** se entrena con 2015–2021 y se prueba con 2022 a septiembre de 2026, incluida la epidemia de 2023, que no vio.

| Métrica | Modelo | Canal endémico |
|---|---|---|
| AUC | 0,984 | 0,790 |
| F1 | 0,76 | 0,70 |
| Recall | 0,69 | 0,59 |
| Precisión | 0,84 | 0,88 |
| AUC en temporada (ene–jun, con casos) | 0,932 | — |
| PR-AUC en brotes nuevos (distrito aún bajo umbral; tasa 1,7%) | 0,62 | — |
| Brier (error de probabilidad) | 0,022 | — |
| MAE de casos a 4 semanas | 12,6 | 27,1 (persistencia) |
| Cobertura P10–P90 | 95% | — |

Otras enfermedades (AUC): leptospirosis 0,78 · EDA 0,78 · golpe de calor 0,74 · IRA 0,84.

**Lectura honesta:** el AUC global está inflado por semanas fáciles, como la temporada seca o los distritos de altura. La métrica exigente es anticipar un brote nuevo. La precisión del canal endémico es algo mayor porque casi nunca alerta; el modelo gana en recall y en el resto.

**Lluvias extremas:** días-distrito sobre el umbral extremo por año: 2017 = 112, 2023 = 45 (no usado para fijar umbrales), años normales ≈ 0–18. No hay inventario público de inundaciones por distrito, así que no se validó contra eventos etiquetados.

## Monitoreo y reentrenamiento
`monitor.py` mide cada semana (a) la deriva de cada variable con PSI frente a la misma época de 2015–2021 y el % de valores fuera del rango de entrenamiento, y (b) el Brier y la calibración por trimestre. Regla: reentrenar si hay deriva fuerte (PSI > 0,25) en variables importantes, si el Brier reciente supera 1,5× el de validación o si la calibración se desvía más de 10 puntos.

`retrain.py` entrena un **retador** con todo lo etiquetado hasta 26 semanas atrás y lo compara con el campeón en esas 26 semanas, que ninguno vio. Se promueve si el Brier mejora ≥ 5% sin perder más de 0,01 de AUC; luego se vuelve a ajustar con todos los datos. Cada entrenamiento queda en `reports/experiments.jsonl` y, si está instalado, en MLflow.

**Resultado actual:** el mar Niño 1+2 está en +5,3 °C (máximo en entrenamiento: 2,7 °C; 61,5% de las semanas recientes fuera de rango) y el Brier reciente es 0,053 frente a 0,022. El retador logra Brier 0,034 contra 0,049 del campeón (−32%) y se promueve. "Hoy" se predice con el modelo de producción; los replays de 2017 y 2023 con el campeón de evaluación.

## Limitaciones y riesgos
- Los casos son **simulados**. Las métricas validan el método, no la precisión con datos reales del MINSA.
- Los modelos logísticos de las otras 4 enfermedades no usan índices de El Niño (hoy están fuera del rango y la logística extrapolaría); no se reentrenan con el campeón–retador, solo el modelo de dengue.
- La población y el acceso a agua son aproximados. Los distritos vecinos comparten celda climática ERA5 (≈ 25 km).
- El plan de brigadas asume beneficio lineal con la cobertura, una efectividad del 30% y costos de ejemplo; no incluye traslados ni efectos entre distritos. Es una guía de priorización.
- **Drift:** el sistema lo vigila, pero la deriva puede deberse a un cambio real (más pruebas, nuevos serotipos); un retador no lo arregla si el dato cambió de significado.
- **Sesgo:** los distritos con menos notificación quedan subestimados. Se mitiga con la variable de acceso a agua y revisando las métricas por departamento.
- **IA generativa:** solo redacta a partir de los números del modelo; el prompt le prohíbe diagnosticar o recetar y, en los modos con cifras, se le entregan valores ya calculados para que no haga cuentas. Si no responde se usa un texto de respaldo.

## Reproducibilidad
- Semilla fija y flujo aleatorio propio por distrito: agregar semanas nuevas no cambia las ya simuladas (hay un test).
- Versiones exactas en `ml/requirements.txt`; `run_pipeline.sh` reproduce todo de punta a punta con el mismo resultado.
- ONNX verificado contra scikit-learn (diferencia < 1e-6) para el modelo de evaluación y el de producción.
- 12 pruebas del pipeline y 19 de la API; el optimizador de Python y el del navegador se comparan con los mismos datos.
