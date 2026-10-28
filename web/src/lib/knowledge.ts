// Base de conocimiento de la IA: lo único que puede afirmar además de los datos que recibe en cada consulta.
// Sale del glosario del sitio y de las fuentes oficiales citadas en el README. Si algo no está aquí ni en los datos,
// la IA debe decir que ese dato no lo tenemos.
import { GLOSARIO } from "./glossary.ts";

const CLAVES = [
  "nino", "nino12", "oni", "prob_brote", "canal_endemico", "nivel", "casos_esperados", "confianza", "modelo_clima",
  "lluvias_extremas", "enfermedades", "contexto_oficial", "establecimientos", "reportes", "calibracion", "golpe_calor", "validacion_externa",
] as const;

// Cifras oficiales transcritas de ml/reference/contexto_oficial_2026.json (hay una prueba que comprueba que coinciden).
export const HECHOS_OFICIALES = [
  "Casos de dengue 2026 al 12 de septiembre (CDC Perú, confirmados y probables): Tumbes 1757 (81% más que en 2025, cuando fueron 970), Piura 10644 (944% más, antes 1020) y Lambayeque 6130 (832% más, antes 658).",
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

export const CONOCIMIENTO = [
  ...CLAVES.map((k) => {
    const e = GLOSARIO[k];
    return `- ${e.titulo}: ${[e.que, e.leer, e.ojo].filter(Boolean).join(" ")}`;
  }),
  DEL_SITIO,
  HECHOS_OFICIALES,
  MEDIDAS_MINSA,
].join("\n");
