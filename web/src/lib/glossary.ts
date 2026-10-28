// Glosario del sitio. Una sola fuente de verdad para dos usos:
//  1. Los botones "?" abren estas entradas (se muestran como texto plano).
//  2. La IA solo puede apoyarse en estas definiciones y en los datos que recibe (ver knowledge.ts).
// Todo está escrito en lenguaje simple y coincide con lo que calcula el pipeline de ml/.

export interface Entrada {
  titulo: string;
  /** Qué es, en una o dos frases. */
  que: string;
  /** Cómo leerlo o usarlo. */
  leer?: string;
  /** Una advertencia o límite honesto. */
  ojo?: string;
}

export const GLOSARIO: Record<string, Entrada> = {
  // ---------- El fenómeno y los datos del clima ----------
  nino: {
    titulo: "El Niño costero",
    que: "Es un calentamiento anormal del mar frente a la costa norte del Perú. Trae más lluvia, más calor y a veces inundaciones. Esas condiciones ayudan a que se reproduzca el zancudo del dengue y a que el agua se contamine.",
    leer: "Mira cuánto sube el mar sobre lo normal (Niño 1+2) y cuánta lluvia cae en tu distrito: son las dos señales que más usa el modelo.",
    ojo: "El ENFEN mantiene el estado de alerta de El Niño costero (comunicado 16-2026). Este sitio no emite alertas oficiales: apoya la decisión y no reemplaza al MINSA ni al ENFEN.",
  },
  nino12: {
    titulo: "Mar Niño 1+2",
    que: "Cuántos grados está el mar frente a Perú y Ecuador por encima de lo normal para esa época. Es una medida semanal de NOAA.",
    leer: "Un valor de +0,5 °C ya es cálido. Hoy estamos muy por encima: es un nivel que el modelo no vio al entrenarse, por eso el monitoreo lo marca.",
  },
  oni: {
    titulo: "Índice ONI",
    que: "Es el índice con el que se declara El Niño en el Pacífico central. Promedia tres meses de la temperatura del mar en la región Niño 3.4.",
    leer: "Si se mantiene sobre +0,5 °C varios meses seguidos, se considera que hay El Niño.",
  },
  lluvias_extremas: {
    titulo: "Lluvias extremas",
    que: "Compara la lluvia acumulada en 3 días con la historia del propio distrito (2015 a 2021). Lluvia intensa es el percentil 99 y lluvia extrema el percentil 99,9: pasa muy pocas veces.",
    leer: "Se usa el pronóstico de 16 días de Open-Meteo para avisar con tiempo. El gráfico muestra la lluvia diaria, el acumulado y los dos umbrales.",
    ojo: "No es un modelo entrenado con inundaciones reales (no hay inventario público por distrito): es un índice de umbrales, el enfoque habitual de las alertas de lluvia.",
  },

  // ---------- Qué predice el modelo ----------
  prob_brote: {
    titulo: "Probabilidad de brote",
    que: "Qué tan probable es que, en alguna de las próximas 4 semanas, los casos de dengue del distrito pasen el umbral de brote.",
    leer: "30% o más ya merece atención y 60% o más es riesgo alto. Sirve sobre todo para comparar un distrito con otro.",
    ojo: "Es una probabilidad, no una certeza: con 70% todavía hay 3 de cada 10 veces que no pasa.",
  },
  canal_endemico: {
    titulo: "Umbral de brote (canal endémico)",
    que: "Es lo que es normal para ese distrito en esa época del año, según su propia historia. Se considera brote cuando los casos de la semana pasan el percentil 75 de esa historia y hay al menos 5 casos.",
    leer: "En los gráficos es la línea punteada: los casos por encima de ella son semanas en brote.",
  },
  nivel: {
    titulo: "Semáforo de riesgo",
    que: "Resume la probabilidad de brote en tres colores: alto desde 60%, medio de 30% a 59% y bajo por debajo de 30%.",
    leer: "El semáforo del ciudadano toma el peor entre el riesgo de enfermedades y el de lluvias extremas.",
  },
  casos_esperados: {
    titulo: "Casos esperados y rango",
    que: "Los casos que el modelo espera en las próximas 4 semanas. Se muestra el valor probable (P50) y un rango entre un escenario optimista (P10) y uno pesimista (P90).",
    leer: "Si el rango es muy ancho, hay mucha incertidumbre. Un buen rango debería contener lo que realmente pasa 8 de cada 10 veces.",
    ojo: "Con solo clima el rango acierta alrededor del 60% de las veces, menos de lo ideal: úsalo como orientación.",
  },
  confianza: {
    titulo: "Confianza del modelo",
    que: "Qué tan firme es la estimación: combina qué tan lejos está la probabilidad del 50% y qué tan estrecho es el rango de casos. Puede ser alta, media o baja.",
    ojo: "Cuando el modelo usa solo clima, la confianza nunca pasa de media, porque no conoce los casos recientes.",
  },
  modelo_clima: {
    titulo: "Estimación solo con clima",
    que: "Los casos oficiales por distrito llegan con meses de retraso (el último que tenemos es del 29 de diciembre de 2025). Mientras no haya casos recientes, el modelo de hoy usa solo clima, mar y calendario.",
    leer: "Sirve para decidir qué distritos vigilar primero: ordena bien el riesgo entre distritos.",
    ojo: "Sin ajuste, se queda muy corto en las epidemias. Por eso hoy se corrige con el acumulado oficial del año por departamento (informe del CDC), y aun así tiende a quedarse a la mitad: contrástalo con las cifras del CDC.",
  },
  enfermedades: {
    titulo: "Otras enfermedades",
    que: "Además del dengue se estima el riesgo de leptospirosis, diarreas (EDA), infecciones respiratorias (IRA) y golpe de calor. Son modelos más simples que dicen si el distrito tendrá una semana de casos por encima de lo habitual.",
    ojo: "El golpe de calor es simulado a partir de la temperatura, porque no hay datos abiertos por distrito.",
  },

  // ---------- Herramientas del panel de autoridad ----------
  acierto_alerta: {
    titulo: "Acierto de la alerta",
    que: "En los replays (2017 y 2023) sabemos lo que realmente pasó. Aquí se cuenta en cuántos distritos el modelo acertó si habría brote o no, y en cuántos los casos reales cayeron dentro del rango previsto.",
    leer: "El modelo de ese replay se entrenó solo con datos hasta 2021: nunca vio esa epidemia.",
  },
  replay: {
    titulo: "Replay de una epidemia pasada",
    que: "Vuelve a una semana de 2017 o de 2023, justo antes del pico, y muestra lo que el modelo habría dicho entonces junto con lo que realmente pasó (casos del CDC-MINSA).",
  },
  contexto_oficial: {
    titulo: "Contexto oficial 2026",
    que: "Cifras publicadas por el CDC y el Minsa este año: casos de dengue por departamento y a nivel nacional, y la alerta epidemiológica N.° 008-2026.",
    leer: "Se muestran junto al ranking para contrastarlo: hoy Piura tiene unas 10 veces los casos de 2025.",
    ojo: "Son totales por departamento, no por distrito. No se usan para entrenar el modelo.",
  },
  simulador: {
    titulo: "Simulador: ¿y si cambia el clima?",
    que: "Mueve la lluvia o la temperatura y el modelo recalcula el riesgo del distrito al instante, dentro de tu navegador. 100% de lluvia equivale al pico de 2023 en ese distrito.",
    ojo: "Es un ejercicio de sensibilidad, no un pronóstico.",
  },
  historia: {
    titulo: "Historia y pronóstico",
    que: "Casos por semana del distrito frente al umbral de brote. La zona sombreada es el pronóstico del modelo para las próximas 4 semanas y las barras de abajo son la lluvia.",
    leer: "Donde no hay casos oficiales se ve el hueco y la nota «sin datos»: nunca se dibuja como cero. En Piura se agregan, en verde, los casos del Gobierno Regional.",
  },
  mapa_calor: {
    titulo: "Mapa de calor",
    que: "Cada fila es un distrito y cada columna una semana. Más oscuro significa más casos por cada 100 mil habitantes. Gris es que no hay dato oficial.",
  },
  temporadas: {
    titulo: "Comparar temporadas",
    que: "Superpone, semana a semana del año, 2017 (Niño costero), 2023 (ciclón Yaku y Niño) y la temporada más reciente con datos.",
  },
  comparar: {
    titulo: "Comparar distritos",
    que: "Pone dos distritos en la misma gráfica en casos por 100 mil habitantes, para que la comparación sea justa aunque tengan distinta población.",
  },
  establecimientos: {
    titulo: "Dónde se concentra la atención",
    que: "Los establecimientos de salud que más casos de dengue notificaron en el distrito en las últimas 8 semanas, con su tendencia frente a las 8 anteriores. Los datos son del Gobierno Regional de Piura.",
    ojo: "Es la carga de notificación, no una predicción por establecimiento. Solo existe para Piura y llega hasta el corte de la fuente (junio de 2026).",
  },
  reportes: {
    titulo: "Reportes ciudadanos",
    que: "Avisos anónimos de vecinos («veo criaderos» o «hay personas con fiebre»). Solo se guarda un conteo por distrito y semana: sin nombre, sin ubicación y sin texto.",
    ojo: "Son señales sin verificar: hay que confirmarlas en campo y nunca alimentan el modelo.",
  },

  // ---------- Plan de acción ----------
  plan_brigadas: {
    titulo: "Plan de brigadas",
    que: "Con las brigadas que tienes disponibles, el optimizador busca en qué distritos evitan más casos y lo compara con repartir parejo o solo por probabilidad.",
    leer: "Los casos evitados se muestran como un valor probable y un rango, según el escenario que elijas.",
    ojo: "Efectividad, habitantes por brigada y costos son supuestos de ejemplo: cada DIRESA debe validarlos.",
  },
  casos_evitados: {
    titulo: "Casos evitados",
    que: "Cuántos casos de dengue se evitarían con el plan, según la efectividad que supongas. Se muestra el valor del criterio elegido (probable o prudente) y el rango del modelo.",
    ojo: "Depende de supuestos de ejemplo (efectividad, habitantes por brigada): es una guía de priorización, no una orden de operaciones.",
  },
  ahorro_neto: {
    titulo: "Ahorro neto estimado",
    que: "Lo que se ahorraría en atención de casos menos lo que cuestan las brigadas, con los costos de ejemplo que figuran en los supuestos.",
    ojo: "Los costos son de ejemplo: la cifra real debe salir de la DIRESA o de un estudio de costos.",
  },
  equilibrio: {
    titulo: "Equilibrio: cuándo se paga el plan",
    que: "La efectividad mínima de las brigadas para que lo que se ahorra en casos evitados iguale lo que cuestan. Si la efectividad real es menor, el plan pierde dinero (aunque igual puede salvar a personas).",
    leer: "Mientras más baja sea esta cifra frente a la efectividad que supones, más holgado es el plan.",
    ojo: "Usa los costos de ejemplo: la cifra real depende de lo que cuesta atender un caso en esa DIRESA.",
  },
  retorno_sol: {
    titulo: "Retorno por sol invertido",
    que: "Cuántos soles se ahorran en atención de casos por cada sol que se gasta en brigadas. Más de 1 significa que el plan se paga solo.",
    ojo: "Depende de la efectividad y de los costos de ejemplo.",
  },
  efectividad: {
    titulo: "Efectividad de una brigada",
    que: "Qué parte de los casos esperados evita una brigada que cubre por completo un distrito. Con cobertura parcial el efecto es menor.",
    ojo: "El valor inicial (30%) es un supuesto de ejemplo.",
  },

  // ---------- Calidad del modelo ----------
  auc: {
    titulo: "AUC",
    que: "Mide si el modelo pone los distritos y semanas con brote por delante de los que no tuvieron. 0,5 es como tirar una moneda y 1,0 es perfecto.",
    leer: "Con casos recientes el AUC es de 0,94; solo con clima, de 0,69.",
  },
  brier: {
    titulo: "Error de probabilidades (Brier)",
    que: "Mide qué tan cerca estuvieron las probabilidades de lo que pasó. Mientras menor, mejor. Se compara con «sin información», que es predecir siempre la tasa de brote del entrenamiento.",
    ojo: "Si el error del modelo no es menor que el de «sin información», el modelo no aporta.",
  },
  ic95: {
    titulo: "Intervalo de confianza del 95%",
    que: "El rango donde probablemente está el valor verdadero de una métrica. Se calcula remuestreando distritos, porque las semanas de un mismo distrito se parecen entre sí.",
    leer: "Si dos intervalos no se tocan, la diferencia no es casualidad.",
  },
  calibracion: {
    titulo: "Calibración de la intensidad",
    que: "El modelo ordena bien los distritos, pero en las epidemias grandes se quedaba corto. Con casos recientes se compara lo observado con lo previsto en las últimas 4 semanas ya conocidas y se reescalan los casos esperados.",
    ojo: "Con casos recientes se calibra con las últimas 4 semanas. Con solo clima se calibra, de forma más tosca, con el acumulado oficial del año por departamento.",
  },
  psi: {
    titulo: "Cambio en los datos (PSI)",
    que: "Compara los datos recientes con los de entrenamiento. Menos de 0,10 es estable y más de 0,25 es un cambio fuerte.",
    leer: "Hoy el mar Niño 1+2 está fuera del rango con el que se entrenó el modelo.",
  },
  campeon_retador: {
    titulo: "Campeón contra retador",
    que: "Cada semana se entrena un modelo nuevo (retador) y se compara con el actual (campeón) sobre un año que ninguno vio. El retador solo pasa a producción si mejora el error en al menos 5%.",
  },
  progresiva: {
    titulo: "Evaluación año por año",
    que: "Para cada año se entrena con todo lo anterior y se prueba en ese año. Así se ve qué pasa cuando el modelo ya vio la epidemia anterior.",
  },
  validacion_externa: {
    titulo: "Validación externa",
    que: "Prueba del modelo de hoy con casos de Piura de 2026 que nunca vio (Gobierno Regional). Como sus conteos no son comparables con los del CDC, la actividad alta se define de forma relativa a cada distrito.",
  },

  // ---------- Cómo leer cada página ----------
  panel_autoridad: {
    titulo: "Cómo leer el panel de autoridad",
    que: "Arriba eliges el escenario (Hoy o un replay de 2023 o 2017) y el departamento. Luego ves el resumen, el mapa y el ranking de distritos. Al elegir un distrito aparecen sus acciones y las enfermedades; lo demás está en apartados que se abren con un toque.",
    leer: "Empieza por el ranking: los distritos están ordenados por probabilidad de brote. Cada apartado cerrado trae una línea con lo más importante.",
  },
  panel_ciudadano: {
    titulo: "Cómo leer la vista del ciudadano",
    que: "Elige tu distrito y verás un semáforo con lo más importante. Debajo, cada riesgo se abre para ver qué hacer en casa y cuándo ir al centro de salud.",
    leer: "Con «Escuchar este aviso» se lee en voz alta, y con el botón de las dos letras se agranda el texto.",
  },
  panel_plan: {
    titulo: "Cómo leer el plan de acción",
    que: "Indica cuántas brigadas tienes y el sitio calcula en qué distritos evitan más casos. Los supuestos (efectividad, habitantes por brigada, costos) están en un apartado y se pueden cambiar.",
    ojo: "Los costos y la efectividad son supuestos de ejemplo, para validar con la DIRESA.",
  },
  panel_modelo: {
    titulo: "Cómo leer la página del modelo",
    que: "Resume cómo funciona el modelo y qué tan bien acierta, incluidas sus fallas. Cada tema es un apartado que se abre solo si quieres el detalle.",
    leer: "Si solo quieres lo esencial, lee el aviso de arriba y las dos tarjetas: con casos recientes y solo con clima.",
  },

  casos_2026_cdc: {
    titulo: "Casos 2026 por distrito (CDC)",
    que: "El CDC publica cada semana un informe de dengue con los distritos que más casos tienen: casos acumulados del año, tasa por 100 mil habitantes, casos de la última semana y defunciones. Los demás distritos se agrupan en «demás distritos».",
    leer: "Se compara con los casos del mismo periodo de 2025. Si un distrito no figura, no significa que no tenga casos: no está entre los de mayor número.",
    ojo: "Es un acumulado, no una serie semanal: no alimenta el modelo con casos recientes. Se usa para contrastar y calibrar.",
  },
  ajuste_acumulado: {
    titulo: "Ajuste con el acumulado oficial",
    que: "El modelo de solo clima se quedaba corto en las epidemias. Se estima cuántos casos tuvo el piloto en lo que va del año (casos del departamento por la participación histórica del piloto) y se compara con lo que el modelo había previsto para esas semanas. La razón, amortiguada, reescala los casos esperados.",
    leer: "En la prueba histórica 2022 a 2025 el sesgo bajó de 6,5 a 2 veces, el rango P10 a P90 pasó de 64% a 83% y el error por distrito bajó 14%.",
    ojo: "Corrige la magnitud, no el reparto entre distritos. Hoy aun así tiende a quedarse a la mitad de lo que reporta el CDC.",
  },
  panel_impacto: {
    titulo: "Cómo leer alimentos y suministros",
    que: "Arriba ves cuántos distritos tienen lluvia intensa o extrema pronosticada, cuántas personas no tienen agua por red en ellos y cuántos suministros de salud harían falta. Abajo, la tabla por distrito y los alimentos y cultivos en riesgo, cada uno con su fuente.",
    ojo: "Los alimentos se cruzan por departamento, no por distrito: no hay datos abiertos de cultivos por distrito.",
  },
  suministros: {
    titulo: "Suministros de salud sugeridos",
    que: "Pruebas rápidas de dengue y camas de observación que haría falta tener según los casos esperados del distrito. Las pruebas son 1,5 veces los casos del escenario pesimista (P90) y las camas el 4% de ese mismo valor.",
    leer: "Son un punto de partida para planificar compras y reservas, no una orden. Se actualizan cuando cambia el pronóstico.",
    ojo: "Son reglas de ejemplo del sitio: la DIRESA debe validarlas con su experiencia y su inventario.",
  },
  exposicion_agua: {
    titulo: "Personas sin agua por red",
    que: "Habitantes del distrito que no tienen conexión de agua por red pública (población por la proporción sin acceso). Con inundaciones, sus fuentes se contaminan o se cortan y el riesgo de diarreas y leptospirosis sube.",
    ojo: "El acceso a agua por red de cada distrito es aproximado (orden de magnitud del INEI).",
  },
  alimentos: {
    titulo: "Alimentos y cultivos en riesgo",
    que: "Cultivos y abastecimiento que El Niño 2026-2027 pone en riesgo en Tumbes, Piura y Lambayeque, con la cifra, la fuente, la fecha y el enlace de cada dato. Se distingue lo oficial (Senamhi, Midagri, Cenepred, ENFEN) de lo que es una estimación de consultoras o gremios.",
    ojo: "No se incluye pesca ni acuicultura: las fuentes revisadas no traen cifras verificables.",
  },
  nino_2027: {
    titulo: "Qué viene en 2027",
    que: "Lo que pronostican los centros de Estados Unidos (NOAA) sobre El Niño: qué tan fuerte será cada temporada y cómo evolucionaría el mar frente a Perú. Se descarga por script y se muestra con sus fechas y enlaces.",
    leer: "NOAA habla de El Niño global (Pacífico central). El que declara «El Niño costero» en el Perú y su magnitud es el ENFEN. Hoy los dos coinciden en un evento muy fuerte.",
    ojo: "Son probabilidades y se actualizan cada mes. Un pronóstico fuerte no fija la fecha ni la magnitud de las lluvias en cada distrito.",
  },
  noaa_estado: {
    titulo: "Estado del sistema de alerta de NOAA",
    que: "NOAA mantiene un semáforo de El Niño: «vigilancia» cuando es probable que se forme, «aviso» (advisory) cuando ya está presente y se espera que continúe, y «final» cuando se disipa.",
    leer: "«Aviso de El Niño» significa que El Niño ya está en marcha.",
  },
  noaa_probabilidades: {
    titulo: "Probabilidades oficiales de NOAA",
    que: "Para cada temporada de 3 meses, la probabilidad de El Niño, de neutral y de La Niña, y dentro de El Niño, qué tan fuerte: débil, moderado, fuerte o muy fuerte. Lo elabora un equipo de unas 10 personas con varios modelos y observaciones.",
    leer: "Se mide en la región Niño 3.4 del Pacífico central con el índice RONI. Se actualiza el segundo jueves de cada mes.",
  },
  evento_historico: {
    titulo: "Evento histórico",
    que: "NOAA calcula la probabilidad de que el índice de 3 meses llegue a +2,5 °C o más, lo que superaría todos los El Niño registrados desde 1950 (incluidos 1982–83, 1997–98 y 2015–16).",
    ojo: "Que el índice global sea histórico no dice por sí solo cuánta lluvia caerá en cada distrito del norte del Perú.",
  },
  cfsv2: {
    titulo: "Modelo CFSv2 y la región Niño 1+2",
    que: "CFSv2 es el modelo climático de NOAA que corre 40 veces con pequeñas diferencias iniciales. Para la región Niño 1+2 (el mar frente a Perú y Ecuador) se muestra el promedio y el rango entre el 10% y el 90% de esas corridas.",
    ojo: "Es un solo modelo y no es el pronóstico oficial. Cuando la banda es ancha, el modelo no sabe bien qué pasará.",
  },
  semana_base: {
    titulo: "Semana base",
    que: "La semana desde la que el modelo mira hacia adelante. Hoy es la última semana con clima observado; en un replay es unas tres semanas antes del pico de esa epidemia.",
  },

  // ---------- Otros ----------
  alertas: {
    titulo: "Alertas en el celular",
    que: "Avisos de tu distrito a tu celular, incluso con la app cerrada. Cada lunes se avisa si el riesgo es alto, si sube o si bajó.",
    leer: "Solo se guarda el distrito y la dirección técnica del navegador: ningún dato personal.",
  },
  ia: {
    titulo: "Qué puede y qué no puede hacer la IA",
    que: "La IA solo redacta explicaciones con los datos de este sitio y con las definiciones de este glosario. Habla de El Niño costero, del dengue y las enfermedades asociadas, de las lluvias y de cómo leer los datos.",
    ojo: "No diagnostica, no receta medicamentos, no responde sobre otros temas y no inventa cifras. Si una respuesta incluye números que no están en los datos, se descarta y se muestra el texto de respaldo.",
  },
  golpe_calor: {
    titulo: "Golpe de calor (simulado)",
    que: "No existe una fuente abierta de golpe de calor por distrito, así que se simula a partir de la temperatura máxima real.",
  },
};

export type ClaveGlosario = keyof typeof GLOSARIO;
