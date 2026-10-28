// Base de conocimiento de la IA: lo único que puede afirmar además de los datos que recibe en cada consulta.
// Sale del glosario del sitio y de las fuentes oficiales citadas en el README. Si algo no está aquí ni en los datos,
// la IA debe decir que ese dato no lo tenemos.
import { GLOSARIO } from "./glossary.ts";
import { CDC2026 } from "./cdc2026.ts";
import { PRODUCTOS } from "./impacto_alimentos.ts";

const CLAVES = [
  "nino", "nino12", "oni", "prob_brote", "canal_endemico", "nivel", "casos_esperados", "confianza", "modelo_clima",
  "lluvias_extremas", "enfermedades", "contexto_oficial", "casos_2026_cdc", "ajuste_acumulado", "suministros", "exposicion_agua", "alimentos", "establecimientos", "reportes", "calibracion", "golpe_calor", "validacion_externa",
] as const;

// Cifras oficiales: el informe semanal del CDC por distrito (cdc2026.ts lo genera el pipeline) y la nota del Minsa
// (ml/reference/contexto_oficial_2026.json). Hay una prueba que comprueba que coinciden con los archivos de referencia.
const dep = Object.entries(CDC2026.departamentos)
  .map(([n, v]) => `${n} ${v.casos_2026} casos (${v.casos_2025} en el mismo periodo de 2025; ${v.casos_ultima_semana} en la última semana)`)
  .join("; ");
const top = CDC2026.top.map((d) => `${d.distrito} (${d.departamento}) ${d.casos_2026} casos, ${d.casos_ultima_semana} en la última semana`).join("; ");
export const HECHOS_OFICIALES = [
  `Casos de dengue 2026 hasta la semana epidemiológica ${CDC2026.semana} (CDC Perú, confirmados y probables): ${dep}.`,
  `Distritos del piloto con más casos en 2026: ${top}.`,
  "Todo el país hasta la semana epidemiológica 40 de 2026: 71256 casos de dengue (122% más que en 2025), 75 fallecidos, 27 de ellos menores de edad. Diarreas (EDA): 1159363 episodios (11,3% más). Leptospirosis: 13235 casos (85,5% más).",
  "El Minsa emitió la alerta epidemiológica N.° 008-2026 el 20 de octubre de 2026. El ENFEN mantiene el estado de alerta de El Niño costero (comunicado oficial 16-2026).",
].join("\n");

export const MEDIDAS_MINSA = [
  "Medidas que recomienda el Minsa (alerta epidemiológica 008-2026): eliminar el agua acumulada en recipientes y tapar los depósitos de agua; consumir agua potable o desinfectada guardada en recipientes limpios y tapados;",
  "evitar el contacto con aguas de inundación y, si es inevitable, usar botas y guantes; lavarse las manos con agua segura y jabón; completar las vacunas;",
  "en zonas priorizadas, aplicarse las dosis de la vacuna contra el dengue que indique el personal de salud (de 10 a 20 años en Tumbes y Piura; de 10 a 16 años en Lambayeque);",
  "acudir a un establecimiento de salud ante fiebre, diarrea persistente, dificultad para respirar u otros síntomas de alarma; y no automedicarse.",
].join(" ");

const DEL_SITIO = [
  "Sobre el sitio: Alerta Salud Niño cubre 47 distritos de Tumbes, Piura y Lambayeque. Los casos reales son del CDC-MINSA (datos abiertos) hasta el 29 de diciembre de 2025; el clima es de Open-Meteo y el mar de NOAA.",
  "El golpe de calor es simulado. El sitio apoya la decisión: no emite alertas oficiales ni reemplaza al Minsa ni al ENFEN.",
].join(" ");

// Alimentos y cultivos en riesgo, con la misma redacción y las mismas fuentes que la página «Alimentos y suministros».
const ALIMENTOS = "Alimentos y cultivos en riesgo por El Niño 2026-2027 (no hay datos por distrito; no se incluye pesca):" + "\n" +
  PRODUCTOS.map((p) =>
    `- ${p.nombre} (${p.departamentos.join(", ")}): ${p.riesgo}${p.dato ? " " + p.dato : ""} Fuente: ${p.fuentes.map((f) => `${f.medio}, ${f.fecha}`).join("; ")} (${p.tipo === "oficial" ? "cifras oficiales" : "estimación de terceros, no oficial"}).`,
  ).join("\n");

export const CONOCIMIENTO = [
  ...CLAVES.map((k) => {
    const e = GLOSARIO[k];
    return `- ${e.titulo}: ${[e.que, e.leer, e.ojo].filter(Boolean).join(" ")}`;
  }),
  DEL_SITIO,
  HECHOS_OFICIALES,
  ALIMENTOS,
  MEDIDAS_MINSA,
].join("\n");
