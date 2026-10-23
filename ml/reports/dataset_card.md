# Dataset card: Alerta Salud Niño

## Fuentes reales (por API)

| Dato | Fuente | Periodo | Granularidad |
|---|---|---|---|
| Lluvia, temperatura máxima y media, humedad | Open-Meteo Archive API (reanálisis ERA5) | 2015 – hoy | Diaria → semanal, por celda de 0,25° asignada a cada distrito. La descarga es incremental: solo se piden los días nuevos más 10 de solapamiento (ERA5 corrige valores recientes) |
| Pronóstico de lluvia y temperatura | Open-Meteo Forecast API | 16 días | Diaria |
| Anomalía de temperatura del mar Niño 1+2 | NOAA CPC (`wksst9120.for`) | 1990 – hoy | Semanal |
| ONI | NOAA CPC (`oni.ascii.txt`) | 1950 – hoy | Trimestral móvil |

Ninguna de estas fuentes requiere API key y todas son de uso libre. No contienen datos personales.

## Datos simulados (`simulate.py`)

Son casos semanales por distrito de 5 enfermedades, generados a partir del clima real.

**Dengue.** Usa un modelo de renovación: los casos de esta semana son la importación más R_t × los casos recientes (intervalo serial de unas 2 semanas). R_t depende de:
- la lluvia de hace 2 a 6 semanas, que forma criaderos;
- una temperatura óptima cercana a 28 °C;
- la altitud (sobre 2000 m casi no hay vector);
- el agua almacenada en hogares sin red;
- la inmunidad que deja un brote (susceptibles según los casos de las últimas 52 semanas);
- un efecto leve del Niño 1+2.

Se agrega ruido no observado (fumigaciones, microclima) y **subregistro**: entre 15% y 95% de los casos se notifica cada semana.

**Las otras cuatro.** Son conteos con sobre-dispersión (binomial negativa):

| Enfermedad | Qué la impulsa |
|---|---|
| Leptospirosis | Lluvia intensa e inundaciones |
| EDA | Calor, falta de agua segura y daño del desagüe tras inundaciones |
| Golpe de calor | Temperatura máxima sobre 30 °C |
| IRA | Cambios bruscos de temperatura y época fría |

**Historia estable.** Cada distrito y cada proceso (brotes, notificación, otras enfermedades) usan su propio generador aleatorio (semilla + distrito + propósito). Al agregar semanas nuevas, las ya simuladas no cambian: reentrenar cada semana no reescribe el pasado (lo verifica un test).

**Calibración.** Las grandes epidemias simuladas caen en 2017 (Niño costero) y 2023 (ciclón Yaku), igual que en la realidad. Como referencia de orden de magnitud, el MINSA notificó 273 684 casos de dengue a nivel nacional en 2023 (alerta AE-CDC-002-2024).

## Distritos
Son 47 distritos de Tumbes, Piura y Lambayeque, listados en `src/config.py`. La población (orden INEI 2017) y el porcentaje de hogares con agua por red son **aproximados**.

## Siguiente paso con datos reales
Reemplazar `simulate.py` por la carga de las salas situacionales del CDC-MINSA (dengue, leptospirosis, EDA e IRA por distrito y semana) cuando haya un formato tabular disponible. El resto del pipeline no cambia.
