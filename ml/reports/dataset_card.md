# Dataset card: Alerta Salud Niño

## Casos de enfermedad: reales (CDC-MINSA)

Datos abiertos de vigilancia epidemiológica del CDC-MINSA, Plataforma Nacional de Datos Abiertos (www.datosabiertos.gob.pe), licencia **Open Data Commons Attribution (ODC-By)**: hay que citar la fuente. Se descargan solos (`ingest_cases.py`), solo si el archivo cambió (se compara tamaño y fecha).

| Enfermedad | Archivo | Años | Registro |
|---|---|---|---|
| Dengue | `datos_abiertos_vigilancia_dengue_2000_2025_0.csv` | 2000–2025 | un caso por fila |
| Diarreas (EDA) | `…_edas_2000_2025.csv` | 2000–2025 | episodios por ubigeo y semana |
| Infecciones respiratorias (IRA) | `…_iras_2000_2025.csv` (separador `;`) | 2000–2025 | idem |
| Leptospirosis | `…_zoonosis_2000_2025_0.csv` | 2000–2025 | un caso por fila |
| Dengue Piura 2025–2026 | `dataset_dengue_actualizado.csv` (Gobierno Regional de Piura) | 2023, 2025, 2026 (corte 2026-07-02) | un caso por fila |

Nuestros 47 distritos suman 297 681 casos de dengue, 5 501 de leptospirosis, 2 038 405 episodios de EDA y 5 841 555 de IRA.

### Decisiones y límites (con evidencia)

- **Cruce por UBIGEO, no por nombre.** La Ñ viene dañada en origen (Pariñas, Tambo Grande, Ferreñafe).
- **El último año del archivo nacional (2025) es provisional y se descarta.** Piura 2025: el CDC trae 1 117 casos y el Gobierno Regional de Piura 12 242. El dengue de 2025 en Tumbes, Piura y Lambayeque es 0,20, 0,03 y 0,07 veces el de 2024. Cuando salga un archivo con un año más, el anterior pasa a usarse. Por eso la cobertura oficial termina el **2024-12-23**.
- **Ceros solo dentro de la cobertura;** fuera es dato desconocido (NaN), nunca cero.
- **Gobierno Regional de Piura:** su 2023 (semanas 1–19) coincide con el CDC (22 712 vs 22 825), pero hay un salto en el empalme 2024→2025. Se muestra como contexto en los gráficos (hasta 2026-06-22, sin la semana de corte incompleta) y **no se usa para entrenar**.
- Tumbes y Lambayeque no tienen 2026 en ninguna fuente abierta.
- Semanas epidemiológicas: domingo a sábado, la semana 1 contiene el 4 de enero; se asigna al lunes siguiente.
- Un caso notificado no es una infección: más casos pueden ser más contagio, más pruebas o más notificación.

## Datos simulados: solo golpe de calor

No existe fuente abierta de golpe de calor por distrito. Se simula a partir de la temperatura máxima real (`simulate.py`, flujo aleatorio estable por distrito). Está marcado como simulado en el sitio.

## Clima y El Niño: reales

| Dato | Fuente | Periodo | Granularidad |
|---|---|---|---|
| Lluvia, temperatura máxima y media, humedad | Open-Meteo Archive API (reanálisis ERA5) | 2015 – hoy | Diaria → semanal, por celda de 0,25°. Descarga incremental (días nuevos + 10 de solapamiento) |
| Pronóstico de lluvia y temperatura | Open-Meteo Forecast API | 16 días | Diaria |
| Anomalía del mar Niño 1+2 | NOAA CPC (`wksst9120.for`) | 1990 – hoy | Semanal |
| ONI | NOAA CPC (`oni.ascii.txt`) | 1950 – hoy | Trimestral móvil |

## Otros datos

Población, altitud y acceso a agua por red de cada distrito son **aproximados** (orden de magnitud INEI), no un censo.

## Privacidad

Todo es agregado por distrito y semana. No hay datos personales.

## Uso

Apoyo a la decisión; no reemplaza la vigilancia oficial del MINSA ni los comunicados del ENFEN.
