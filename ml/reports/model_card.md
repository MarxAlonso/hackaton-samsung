# Model card: Alerta Salud Niño

## Qué predice

Probabilidad de **brote de dengue en las próximas 4 semanas** (casos de las 4 semanas siguientes sobre el umbral del canal endémico del distrito) y **casos esperados** con rango P10–P50–P90, para 47 distritos de Tumbes, Piura y Lambayeque. Además, riesgo de leptospirosis, EDA, IRA y golpe de calor (regresión logística sobre semanas con casos sobre el percentil 80 del distrito). Los casos son **reales** (CDC-MINSA), salvo el golpe de calor (simulado).

## Dos modelos, por qué

Los casos oficiales llegan con meses de retraso: el último que tenemos es del **2024-12-23**. Se entrenan dos familias:

- **Con casos recientes** (casos de las últimas semanas, del último año, umbral endémico, clima, El Niño, calendario). Se usa en los replays de 2017 y 2023, y se usará "hoy" apenas haya casos de hasta 14 días de antigüedad.
- **Solo clima** (lluvia, temperatura, humedad, Niño 1+2, ONI, calendario, altitud, población, agua). Es el de **hoy**.

Algoritmos: Gradient Boosting (brote) y Gradient Boosting por cuantiles (casos), exportados a ONNX para correr en el navegador; verificados contra scikit-learn (diferencia máxima < 1e-6).

## Evaluación (prueba 2022-01-03 a 2024-11-25; entrenamiento 2015-12-28 a 2021-12-27)

La prueba incluye las epidemias de 2023 y 2024: la tasa de brote es 42,8% frente a ~15% en el entrenamiento.

| Métrica | Con casos | Línea base canal endémico | Solo clima | Línea base clima |
|---|---|---|---|---|
| AUC brote | 0,931 | 0,857 | 0,715 | 0,653 |
| PR-AUC | 0,918 | 0,815 | 0,664 | 0,534 |
| Recall | 76% | 75% | 17% | 4% |
| Brier (menos es mejor) | 0,106 | 0,127 | 0,289 | 0,321 |
| MAE casos (4 semanas) | 40,2 | 58,7 (repetir últimas 4) | 80,1 | 58,7 |
| Casos reales dentro de P10–P90 | 74% | — | 50% | — |
| PR-AUC anticipando un brote **nuevo** | 0,378 (azar 0,109) | — | 0,291 | — |

Evaluación progresiva (entrena con todo lo anterior, prueba un año):

| Año | AUC con casos | Brier con casos | AUC solo clima | Brier solo clima | Brier sin información (con casos / clima) |
|---|---|---|---|---|---|
| 2022 | 0,909 | 0,084 | 0,709 | 0,151 | 0,157 / 0,157 |
| 2023 | 0,934 | 0,101 | 0,726 | 0,401 | 0,520 / 0,520 |
| 2024 | 0,939 | 0,099 | 0,716 | 0,319 | 0,289 / 0,289 |

Otras enfermedades (AUC con casos / solo clima): leptospirosis 0,78 / 0,66; EDA 0,83 / 0,74; golpe de calor 0,75 / 0,75 (simulado); IRA 0,74 / 0,66.

## Lectura honesta

- Con casos recientes funciona bien, pero **subestima la intensidad** de las epidemias 2023–24 (ordena bien, calibra mal).
- **Solo clima ordena qué distritos vigilar primero, pero no calcula cuántos casos habrá**: su Brier es igual o peor que predecir siempre la tasa base y el rango P10–P90 acierta 50%. Por eso su confianza nunca pasa de "media".
- Conseguir los casos de 2026 (Tumbes, Lambayeque) es lo que más mejoraría el sistema.
- No se evaluó contra 2025–2026 porque no hay datos oficiales consolidados.

## Monitoreo y reentrenamiento

Cada semana: deriva de clima y El Niño (PSI), error por trimestre y campeón contra retador en **52 semanas** (un ciclo estacional completo) que ninguno vio al entrenar; se promueve solo si el Brier mejora ≥ 5%. Última corrida: el Niño 1+2 está en +5,3 °C, fuera del rango de entrenamiento (máx. 2,7 °C); en solo clima se mantiene el campeón (mejora 2%) y en la familia con casos se promueve el retador (mejora 18%).

## Usos y límites

Apoyo a la decisión de DIRESA y establecimientos; no reemplaza la vigilancia ni diagnostica. Costos y efectividad del plan de brigadas son supuestos de ejemplo editables (S/ 10 000 por brigada, S/ 800 por caso, 30% de efectividad). La IA solo redacta explicaciones con los números del modelo.
