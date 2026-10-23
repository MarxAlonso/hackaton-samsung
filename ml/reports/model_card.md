# Model card: Alerta Salud Niño

## Qué predice

Probabilidad de **brote de dengue en las próximas 4 semanas** (casos de las 4 semanas siguientes sobre el umbral del canal endémico del distrito) y **casos esperados** con rango P10–P50–P90, para 47 distritos de Tumbes, Piura y Lambayeque. Además, riesgo de leptospirosis, EDA, IRA y golpe de calor (regresión logística sobre semanas con casos sobre el percentil 80 del distrito). Los casos son **reales** (CDC-MINSA), salvo el golpe de calor (simulado).

## Dos modelos, por qué

Los casos oficiales llegan con meses de retraso: el último por distrito que tenemos es del **29 dic. 2025**. Se entrenan dos familias:

- **Con casos recientes** (casos de las últimas semanas, del último año, umbral endémico, clima, El Niño, calendario). Se usa en los replays de 2017 y 2023, y se usará "hoy" apenas haya casos de hasta 14 días de antigüedad.
- **Solo clima** (lluvia, temperatura, humedad, Niño 1+2, ONI, calendario, altitud, población, agua). Es el de **hoy**.

Algoritmos: Gradient Boosting (brote) y Gradient Boosting por cuantiles (casos), exportados a ONNX para correr en el navegador; verificados contra scikit-learn (diferencia máxima < 1e-6).

## Evaluación (prueba 2022-01-03 a 2025-12-01; entrenamiento 2015-12-28 a 2021-12-27)

La prueba incluye las epidemias de 2023 y 2024 y el año bajo de 2025: la tasa de brote es 33,3% frente a ~15% en el entrenamiento. Entre paréntesis, el intervalo de confianza del 95% remuestreando distritos (no filas).

| Métrica | Con casos | Línea base canal endémico | Solo clima | Línea base clima |
|---|---|---|---|---|
| AUC brote | 0,938 (0,927–0,949) | 0,851 | 0,687 (0,659–0,724) | 0,641 |
| PR-AUC | 0,900 | — | 0,516 | — |
| Recall | 75% (71–79%) | 73% | 17% (14–20%) | 4% |
| Brier (menos es mejor) | 0,091 (0,081–0,101) | 0,107 | 0,238 (0,209–0,266) | 0,255 |
| MAE casos (4 semanas) | 30,6 (22,0–41,6) | 44,2 (repetir últimas 4) | 61,2 (41,3–86,4) | 44,2 |
| Casos reales dentro de P10–P90 | 78% (75–80%) | — | 60% (55–65%) | — |
| PR-AUC anticipando un brote **nuevo** | 0,345 (azar 0,080) | — | 0,175 | — |

La ventaja del modelo con casos sobre el criterio del MINSA es de +0,087 de AUC (intervalo +0,072 a +0,102): no es casualidad. La del modelo solo clima sobre el calendario es de +0,046 (+0,024 a +0,069): real pero modesta.

Evaluación progresiva (entrena con todo lo anterior, prueba un año):

| Año | Brotes | AUC con casos | Brier con casos | AUC solo clima | Brier solo clima | Brier sin información |
|---|---|---|---|---|---|---|
| 2022 | 19% | 0,909 | 0,084 | 0,709 | 0,151 | 0,157 |
| 2023 | 68% | 0,934 | 0,101 | 0,726 | 0,401 | 0,520 |
| 2024 | 39% | 0,935 | 0,099 | 0,700 | 0,299 | 0,274 |
| 2025 | 5% | 0,935 | 0,051 | 0,805 | 0,100 | 0,077 |

Otras enfermedades (AUC con casos / solo clima): leptospirosis 0,78 / 0,65; EDA 0,85 / 0,72; golpe de calor 0,75 / 0,74 (simulado); IRA 0,74 / 0,66.

## Calibración de la intensidad

El modelo ordena bien los distritos pero se quedaba corto en las epidemias: con casos recientes, lo observado fue 1,45 veces lo previsto en 2023 y 1,81 en 2024 (solo clima: 7,9 y 21,7 veces). Con casos recientes se aplica un **factor de intensidad**: la razón entre lo observado y lo previsto en las últimas 4 semanas ya conocidas (acotada a 0,5–2 veces), que reescala P10, P50 y P90. Solo usa información de ese día.

| Año | Observado ÷ previsto (antes → después) | Rango P10–P90 acierta (antes → después) |
|---|---|---|
| 2022 | 1,08 → 0,76 | 82% → 84% |
| 2023 | 1,45 → 0,96 | 70% → 80% |
| 2024 | 1,81 → 0,98 | 71% → 83% |
| 2025 | 0,80 → 0,83 | 91% → 90% |

Costo: el error medio sube de 30,6 a 32,6 casos (en años tranquilos el ajuste a veces se pasa). Se probó antes una versión con la mediana de los residuos: corregía el sesgo pero empeoraba el error y la cobertura, y se descartó. **Con solo clima no hay resultados recientes para calibrar**: su sesgo sigue ahí y el sitio lo advierte.

## Validación externa con datos de 2026 (Piura, Gobierno Regional)

El modelo de hoy (solo clima) se probó con casos que nunca vio, de enero a mayo de 2026 en 23 distritos de Piura. Como los conteos del Gobierno Regional no son comparables con los del CDC, "actividad alta" es relativa (casos de las próximas 4 semanas sobre el percentil 75 del propio distrito): AUC 0,685 contra 0,579 del calendario; correlación de rangos entre casos previstos y notificados 0,70 (0,61 semana a semana entre distritos). Se probó además agregar los casos recientes del Gobierno Regional como señal de arrastre: AUC 0,717 (+0,032, intervalo −0,046 a +0,110, incluye el cero), así que **no se integra** al modelo. Detalle en `ml/reports/validation_gore.json`.

## Lectura honesta

- Con casos recientes funciona bien. Aun calibrado, el error medio no baja: la calibración arregla el sesgo, no la dispersión.
- **Solo clima ordena qué distritos vigilar primero, pero no calcula cuántos casos habrá**: su Brier es igual o peor que predecir la tasa base en 2024 y 2025, y el rango P10–P90 acierta 60%. Por eso su confianza nunca pasa de "media".
- **El contexto oficial de 2026 lo confirma**: el CDC reporta Piura +944% y Lambayeque +832% frente a 2025 (al 12 de septiembre), mientras que el modelo de hoy marca solo 2 distritos en riesgo alto. Es la subestimación esperable de un modelo solo clima.
- Conseguir los casos 2026 por distrito (Tumbes, Lambayeque; Piura ya existe pero no es comparable) es lo que más mejoraría el sistema.

## Monitoreo y reentrenamiento

Cada semana: deriva de clima y El Niño (PSI), error por trimestre y campeón contra retador en **52 semanas** que ninguno vio al entrenar; se promueve solo si el Brier mejora ≥ 5%. Última corrida: el Niño 1+2 está en +5,3 °C, fuera del rango de entrenamiento (máx. 2,7 °C), y el monitoreo marca "reentrenar"; sin embargo, el retador no supera al campeón en el año evaluado (dic. 2024 a dic. 2025), que fue un año tranquilo y por tanto no pone a prueba un modelo hecho para epidemias. Se mantiene el campeón en ambas familias.

## Usos y límites

Apoyo a la decisión de DIRESA y establecimientos; no reemplaza la vigilancia ni diagnostica. Costos y efectividad del plan de brigadas son supuestos de ejemplo editables (S/ 10 000 por brigada, S/ 800 por caso, 30% de efectividad). La IA solo redacta explicaciones con los números del modelo.
