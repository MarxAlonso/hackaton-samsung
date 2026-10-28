// Alimentos, cultivos y abastecimiento que El Niño 2026-2027 pone en riesgo en Tumbes, Piura y Lambayeque.
// Cada dato trae su fuente, la fecha y el enlace. Se verificó el texto de cada página; las cifras de prensa que son
// ESTIMACIONES de terceros (consultoras, gremios) están marcadas como tales y no son datos oficiales.
//
// Límite que conviene decir en voz alta: NO hay datos abiertos de superficie o producción por cultivo a nivel de
// distrito, así que el cruce con nuestros 47 distritos se hace por departamento y con lo que sí tenemos por distrito
// (pronóstico de lluvia extrema, población y acceso a agua). El detalle por distrito está en el SIEA del MIDAGRI.
// No se incluye pesca ni acuicultura: ninguna de las fuentes revisadas trae cifras verificables.

export interface Fuente {
  medio: string;
  titulo: string;
  fecha: string; // AAAA-MM-DD
  url: string;
  /** De quién son las cifras originales. */
  origen: string;
}

export interface Producto {
  id: string;
  nombre: string;
  icono: string;
  departamentos: ("Tumbes" | "Piura" | "Lambayeque")[];
  /** Qué puede pasar y por qué (con las cifras que trae la fuente). */
  riesgo: string;
  /** Una cifra para destacar. */
  dato?: string;
  /** "oficial": viene del Senamhi, Midagri, Cenepred o ENFEN. "estimacion": cálculo de una consultora o gremio. */
  tipo: "oficial" | "estimacion";
  fuentes: Fuente[];
}

const GESTION_ARROZ_MAPA: Fuente = {
  medio: "Gestión", titulo: "El Niño aumenta riesgo sobre los dos principales cultivos de Perú: temores crecen en el agro", fecha: "2026-09-16",
  url: "https://gestion.pe/economia/el-nino-aumenta-riesgo-sobre-los-dos-principales-cultivos-de-peru-temores-crecen-en-el-agro-noticia/", origen: "Senamhi, Midagri y ENFEN",
};
const GESTION_ENIS: Fuente = {
  medio: "Gestión", titulo: "El Niño haría retroceder a 10 principales cultivos en la próxima campaña agrícola 2026-2027", fecha: "2026-07-15",
  url: "https://gestion.pe/economia/el-nino-haria-retroceder-a-diez-principales-cultivos-de-la-proxima-campana-agricola-2026-2027-noticia/", origen: "Midagri, Encuesta de Intenciones de Siembra 2026-2027 (14 252 informantes)",
};
const FRESHPLAZA_EXPORT: Fuente = {
  medio: "FreshPlaza", titulo: "Extreme El Niño could cost Peru's agricultural export sector nearly $1.5 billion in losses in 2026-2027", fecha: "2026-09-22",
  url: "https://www.freshplaza.com/article/9875296/extreme-el-nino-could-cost-peru-s-agricultural-export-sector-nearly-1-5-billion-in-losses-in-2026-2027/", origen: "Preciso Consultoría, con ENFEN y Promango",
};
const FRESHPLAZA_MANGO: Fuente = {
  medio: "FreshPlaza", titulo: "Peruvian mango crop expected to decline by 60% due to El Niño", fecha: "2026-09-16",
  url: "https://www.freshplaza.com/asia/article/9873340/peruvian-mango-crop-expected-to-decline-by-60-due-to-el-nino/", origen: "Milton Calle (agraria.pe)",
};
const GESTION_PIURA: Fuente = {
  medio: "Gestión", titulo: "Piura inundada en inicio de El Niño: ¿qué riesgo se prevé para su agricultura y carreteras?", fecha: "2026-10-22",
  url: "https://gestion.pe/economia/piura-riesgo-de-inundaciones-que-trae-el-nino-amenaza-al-87-de-su-poblacion-en-el-verano-noticia/", origen: "Cenepred, ENFEN y Senamhi",
};

export const PRODUCTOS: Producto[] = [
  {
    id: "arroz", nombre: "Arroz", icono: "droplet", departamentos: ["Tumbes", "Piura", "Lambayeque"], tipo: "oficial",
    riesgo: "El Senamhi calificó el riesgo del arroz entre alto y muy alto de septiembre a noviembre, con lluvias focalizadas en Tumbes y Piura. En Lambayeque el reservorio Tinajones está al 24% y podría afectar el inicio de la campaña desde diciembre de 2026.",
    dato: "Intención de siembra 2026-2027: Piura −21,2% y Lambayeque −45,0% frente a la campaña anterior.",
    fuentes: [GESTION_ARROZ_MAPA, GESTION_ENIS],
  },
  {
    id: "mango", nombre: "Mango", icono: "sun", departamentos: ["Piura", "Lambayeque"], tipo: "estimacion",
    riesgo: "El Midagri señala que el calor afecta al mango. Promango reporta una floración de 30% en Piura y 25% en Lambayeque. Si llueve en noviembre, podría afectarse hasta 30% de la fruta en Piura por antracnosis, y el mayor impacto se espera de diciembre a enero en Motupe, Olmos y Piura.",
    dato: "Estimación: 178 595 toneladas frente a 557 440 habituales (−US$ 307 millones FOB). Otra proyección calcula una caída cercana al 60%.",
    fuentes: [FRESHPLAZA_EXPORT, FRESHPLAZA_MANGO],
  },
  {
    id: "banano", nombre: "Banano orgánico", icono: "layers", departamentos: ["Piura", "Tumbes"], tipo: "estimacion",
    riesgo: "El 93% del banano orgánico del país se cultiva en Piura y Tumbes, las dos zonas con más lluvia focalizada.",
    dato: "Se proyecta una caída de 16,8% de la producción hacia 2027.",
    fuentes: [FRESHPLAZA_EXPORT],
  },
  {
    id: "frutales", nombre: "Limón, mango, palta y arándanos", icono: "mosquito", departamentos: ["Piura"], tipo: "estimacion",
    riesgo: "Se advierte riesgo para estos cultivos por la combinación de lluvias y calor. La fuente no trae cifras.",
    fuentes: [GESTION_PIURA],
  },
  {
    id: "transporte", nombre: "Carreteras y abastecimiento", icono: "map", departamentos: ["Piura"], tipo: "oficial",
    riesgo: "Hay tramos de carretera en riesgo por lluvias e inundaciones. Consecuencia posible: si se cortan, se interrumpe el traslado de alimentos, agua y medicinas hacia los distritos.",
    dato: "2 501 km en riesgo muy alto y 2 716 km en riesgo alto en la región Piura.",
    fuentes: [GESTION_PIURA],
  },
  {
    id: "poblacion", nombre: "Población y servicios", icono: "users", departamentos: ["Piura"], tipo: "oficial",
    riesgo: "En Piura se identificaron 126 puntos críticos por inundación. 40 distritos, el 87% de la población regional, están en riesgo alto o muy alto. En riesgo muy alto hay 16 distritos, 727 poblados y 317 730 viviendas.",
    dato: "1,1 millones de personas en riesgo muy alto de inundación (Cenepred).",
    fuentes: [GESTION_PIURA],
  },
  {
    id: "agroexportacion", nombre: "Agroexportación del norte", icono: "trendingUp", departamentos: ["Tumbes", "Piura", "Lambayeque"], tipo: "estimacion",
    riesgo: "El ENFEN prevé caudales sobre lo normal en los ríos Tumbes, Chira, Piura y Lambayeque, lo que amenaza los valles agrícolas y la exportación del norte.",
    dato: "Pérdidas estimadas cercanas a US$ 1 500 millones en 2026-2027 (Preciso Consultoría).",
    fuentes: [FRESHPLAZA_EXPORT],
  },
];

export const LIMITES_IMPACTO = [
  "No hay datos abiertos de superficie ni producción por cultivo a nivel de distrito: el cruce con los 47 distritos es por departamento. El detalle distrital está en el SIEA del MIDAGRI.",
  "Las cifras marcadas como estimación son cálculos de consultoras, gremios o expertos citados por la prensa: sirven para dimensionar el riesgo, no son datos oficiales.",
  "No se incluye pesca ni acuicultura: ninguna de las fuentes revisadas trae cifras verificables.",
  "Las cifras de suministros de salud (pruebas rápidas y camas) salen de reglas simples del sitio sobre los casos esperados del modelo y son de ejemplo hasta que la DIRESA las valide.",
];
