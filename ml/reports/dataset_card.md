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

Nuestros 47 distritos suman 300 221 casos de dengue, hasta la semana epidemiológica 53 de 2025 (29 dic. 2025).

### Decisiones y límites (con evidencia)

- **Cruce por UBIGEO, no por nombre.** La Ñ viene dañada en origen (Pariñas, Tambo Grande, Ferreñafe).
- **El 2025 del archivo es válido (se verificó).** Antes se descartaba por parecer incompleto: Piura traía 1 117 casos frente a 12 242 del Gobierno Regional. El informe de la DGE "Dengue al 12/09/2026" (misma fuente oficial del CDC) trae una columna 2025 que coincide exactamente con el archivo hasta la semana 36: Tumbes 970, Piura 1 020, Lambayeque 658, La Libertad 202, San Martín 9 779. 2025 fue un año bajo después de las epidemias de 2023 y 2024. Desde entonces la cobertura llega hasta la última semana del archivo (si el último año está en curso, se excluye su última semana por estar incompleta).
- **Ceros solo dentro de la cobertura;** fuera es dato desconocido (NaN), nunca cero.
- **Gobierno Regional de Piura:** su 2023 (semanas 1–19) coincide con el CDC (22 712 vs 22 825), pero en 2025 sus conteos son unas 11 veces mayores que los del CDC (otro sistema de registro), así que no se pueden empalmar. Se usa **aparte**: como contexto en los gráficos (hasta 2026-06-22, sin la semana de corte incompleta), como validación externa del modelo de hoy y para listar los establecimientos que notifican (la fuente trae `CENTRO_SALUD`). **No se usa para entrenar.**
- **Casos 2026 por distrito: informe semanal del CDC (PDF).** Los CSV de datos abiertos llegan hasta 2025, pero el CDC publica cada semana una sala situacional de dengue (`https://www.dge.gob.pe/portal/docs/vigilancia/sala/{año}/SE{semana}/dengue.pdf`) con una tabla por departamento: casos acumulados del año anterior y del año en curso, tasa por 100 mil, casos de la última semana y defunciones. Solo lista los distritos con más casos y agrupa el resto en «demás distritos» (24 de nuestros 47 distritos figuran hoy). Es un acumulado, no una serie semanal, así que no alimenta el modelo con casos recientes: se usa para mostrar los casos 2026 de cada distrito y para el ajuste con el acumulado oficial. El lector (`ml/src/ingest_dge_sala.py`) prueba desde la semana actual hacia atrás hasta encontrar un PDF real (el sitio responde con una página HTML cuando el informe aún no existe) y guarda el resultado en `ml/reference/`.
- Tumbes y Lambayeque no tienen 2026 por distrito como serie semanal en ninguna fuente abierta. Sí hay totales departamentales oficiales de 2026 (informe de la DGE al 12/09/2026 y alerta epidemiológica N.° 008-2026 del Minsa), transcritos en `ml/reference/contexto_oficial_2026.json` con sus fuentes. Se usan para contrastar y mostrar el contexto, no para entrenar.
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

## Pronósticos de El Niño (NOAA, Estados Unidos)

Tres productos públicos del Climate Prediction Center, descargados por `ml/src/ingest_enso_outlook.py` en cada corrida (si una fuente falla, se conserva la última):

| Producto | Qué trae | Formato |
|---|---|---|
| Official ENSO Strength Probabilities | por temporada de 3 meses, probabilidad de La Niña, neutral y El Niño, y dentro de El Niño por fuerza (débil, moderado, fuerte, muy fuerte); región Niño 3.4, índice RONI | tabla HTML, se actualiza el segundo jueves de cada mes |
| CFSv2 `nino12Mon.nc` | 40 corridas del modelo para la anomalía mensual de la región Niño 1+2 (frente a Perú y Ecuador); el miembro 41 trae lo observado | NetCDF (se lee con netCDF4) |
| ENSO Diagnostic Discussion | estado del sistema de alerta, síntesis, índices del último mes y probabilidad de un evento histórico (RONI ≥ +2,5 °C) | HTML (texto) |

Además, el valor observado mensual de los índices Niño (`rel_mthsst9120.txt`). Límite: NOAA pronostica El Niño global y el mar frente a Perú; el aviso oficial de El Niño costero en el Perú lo emite el ENFEN. El sitio muestra las dos cosas y lo dice.

## Otros datos

Población, altitud y acceso a agua por red de cada distrito son **aproximados** (orden de magnitud INEI), no un censo.

## Privacidad

Todo es agregado por distrito y semana. No hay datos personales.

## Uso

Apoyo a la decisión; no reemplaza la vigilancia oficial del MINSA ni los comunicados del ENFEN.
