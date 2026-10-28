// Protecciones de la IA: qué se acepta como pregunta, qué se acepta como contexto y qué se acepta como respuesta.
// Son funciones puras para poder probarlas (web/scripts/test-guard.mjs). La IA nunca decide sola qué es seguro:
// hay una validación antes (la pregunta), otra durante (el contexto) y otra después (la respuesta).

export const REFUSAL =
  "Solo puedo ayudarte con el fenómeno de El Niño costero, el dengue y las enfermedades asociadas, las lluvias y los datos de este sitio. " +
  "Prueba, por ejemplo: «¿cómo elimino criaderos?» o «¿qué significa riesgo medio?».";
export const MEDICAL =
  "No puedo diagnosticar ni recomendar medicamentos o dosis. Si tú o alguien de tu familia tiene fiebre u otros síntomas, " +
  "acude hoy al establecimiento de salud más cercano y no te automediques.";
export const BLOCKED = "No puedo atender ese tipo de mensaje. Puedo ayudarte con El Niño costero, el dengue y los datos de este sitio.";
export const MAX_QUESTION = 300;
export const MAX_CONTEXT = 12000;

/** Minúsculas, sin tildes, sin caracteres invisibles y con espacios simples. */
export function norm(s: string): string {
  return String(s)
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[\u200b-\u200f\u2028-\u202f\u2060\ufeff]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

// ---- Intentos de manipular a la IA ----
const INJECTION: RegExp[] = [
  /\b(ignora|ignore|olvida|omite|salta|desobedece|anula|desactiva|borra)\b.{0,50}\b(instruccion|regla|restriccion|prohibicion|prompt|indicacion|anterior|limite|filtro)/,
  /\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|above|instruction|rule|prompt|filter|restriction)/,
  /\bprompt\b/,
  /\b(system|sistema)\s*(prompt|message|mensaje|instruction|instruccion)/,
  /\b(actua|actuar|comportate|finge|simula|pretende|imagina que eres|haz de cuenta|hazte pasar|eres ahora|ahora eres|a partir de ahora eres|roleplay|rol de)\b/,
  /\b(jailbreak|dan mode|modo dios|developer mode|modo desarrollador|sin restricciones|sin filtros|sin censura|sin limites)\b/,
  /\b(revela|muestra|repite|imprime|dime|cual es|escribe)\b.{0,40}\b(instruccion|prompt|configuracion|reglas|clave|token|secreto|contrasena|api key)/,
  /\b(que|cual) (modelo|ia|inteligencia artificial) (eres|usas|usan)\b/,
  /<\/?[a-z][^>]*>/,
  /```/,
  /\{\{|\}\}|\$\{/,
  /[a-z0-9+\/=]{60,}/,
];

// ---- Temas que no se atienden aunque mencionen palabras del tema ----
const BLOCKED_TOPICS: RegExp[] = [
  /\b(codigo|programar|programacion|python|javascript|html|css|sql|script|algoritmo|hackear|hackeo|exploit|malware|ransomware)\b/,
  /\b(elecciones|candidato|partido politico|votar|presidente de la republica|congresista|corrupcion)\b/,
  /\b(bomba|explosivo|matar|suicid\w*|droga|cocaina|marihuana|armas?|porno\w*|desnud\w*)\b/,
  /\b(bitcoin|criptomoneda|apuesta|casino|horoscopo|futbol|partido de futbol|pelicula|serie de tv)\b/,
  /\b(traduce|traducir|traduccion|poema|poesia|cancion|chiste|cuento|ensayo|resuelve|ecuacion|tarea de)\b/,
];

// ---- Peticiones médicas: respuesta fija, sin llamar a la IA ----
const MEDICAL_REQUEST =
  /\b(dosis|miligramos?|mg|paracetamol|acetaminofen|ibuprofeno|aspirina|naproxeno|diclofenaco|antibiotico\w*|amoxicilina|ivermectina|cloroquina|suero casero|que (medicina|medicamento|pastilla|remedio|pomada)|que (me )?tomo|que puedo tomar|cuantas pastillas|recetame|recetar|diagnostic\w*|tengo (dengue|leptospirosis|zika|chikungunya)|es dengue|sera dengue|tendre dengue)\b/;

// ---- La pregunta debe tratar de lo que sí sabemos ----
const TOPIC_STEMS = [
  "nino", "fenomeno", "enso", "oni", "niña", "dengue", "zancudo", "mosquito", "aedes", "lluvia", "llov", "inundac", "huaico", "leptospir",
  "diarrea", "eda", "respirator", "calor", "temperatura", "clima", "mar ", "riesgo", "brote", "caso", "distrito", "alerta", "prevenc", "prevenir",
  "salud", "sintoma", "fiebre", "agua", "criadero", "tanque", "balde", "llanta", "vacun", "brigada", "modelo", "predic", "dato", "probabilidad",
  "confianza", "semana", "tumbes", "piura", "lambayeque", "semaforo", "plan", "establecimiento", "cdc", "minsa", "enfen", "grafico", "fuente",
  "significa", "como funciona", "epidemi", "costa", "peru", "enfermedad", "contagio", "picadura", "repelente", "mosquitero", "basura", "roedor",
  "rata", "charco", "humedad", "pronostico", "simulador", "replay", "calibr", "intervalo", "auc", "brier", "reporte", "ayuda", "hola", "gracias",
  "boton", "pagina", "sitio", "app", "alertas", "celular", "notificacion",
];

export type Veredicto =
  | { ok: true; pregunta: string }
  | { ok: false; motivo: "vacia" | "larga" | "inyeccion" | "bloqueada" | "medica" | "fuera_de_tema"; respuesta: string };

export function revisarPregunta(raw: unknown): Veredicto {
  if (typeof raw !== "string") return { ok: false, motivo: "vacia", respuesta: REFUSAL };
  const original = raw.replace(/[\u0000-\u001f\u007f]/g, " ").trim();
  if (!original) return { ok: false, motivo: "vacia", respuesta: REFUSAL };
  if (original.length > MAX_QUESTION) return { ok: false, motivo: "larga", respuesta: `Tu pregunta es muy larga. Escríbela en menos de ${MAX_QUESTION} caracteres.` };
  const n = norm(original);
  if (INJECTION.some((re) => re.test(n))) return { ok: false, motivo: "inyeccion", respuesta: BLOCKED };
  if (MEDICAL_REQUEST.test(n)) return { ok: false, motivo: "medica", respuesta: MEDICAL };
  if (BLOCKED_TOPICS.some((re) => re.test(n))) return { ok: false, motivo: "bloqueada", respuesta: REFUSAL };
  if (!TOPIC_STEMS.some((s) => n.includes(s))) return { ok: false, motivo: "fuera_de_tema", respuesta: REFUSAL };
  return { ok: true, pregunta: original };
}

/** ¿Este texto parece una orden dirigida a la IA? (para limpiar el contexto que llega del navegador) */
export const pareceInstruccion = (s: string) => INJECTION.some((re) => re.test(norm(s)));

// ---- Contexto que llega del navegador: se trata como dato no confiable ----
function limpiar(v: unknown, depth: number): unknown {
  if (depth > 6 || v === null || v === undefined) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "boolean") return v;
  if (typeof v === "string") {
    const s = v.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 280);
    return pareceInstruccion(s) ? "[texto removido]" : s;
  }
  if (Array.isArray(v)) return v.slice(0, 60).map((x) => limpiar(x, depth + 1));
  if (typeof v === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, val] of Object.entries(v as Record<string, unknown>).slice(0, 80)) {
      if (/^[\w áéíóúñÁÉÍÓÚÑ.\-]{1,60}$/.test(k)) out[k] = limpiar(val, depth + 1);
    }
    return out;
  }
  return null;
}

export function limpiarContexto(ctx: unknown): string {
  const json = JSON.stringify(limpiar(ctx, 0) ?? {});
  return json.length > MAX_CONTEXT ? json.slice(0, MAX_CONTEXT) : json;
}

// ---- Respuesta de la IA: solo se acepta si usa cifras que conocemos ----
const NUMERO = /\d{1,3}(?:[ .,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?/g;
const PERCENTILES_Y_UMBRALES = new Set([10, 25, 30, 50, 60, 75, 80, 90, 95, 99, 99.9, 100]);

export function numerosDe(texto: string): number[] {
  const out: number[] = [];
  for (const tok of texto.match(NUMERO) ?? []) {
    const t = tok.replace(/ /g, "");
    const v = /^\d{1,3}([.,]\d{3})+$/.test(t) ? Number(t.replace(/[.,]/g, "")) : Number(t.replace(",", "."));
    if (Number.isFinite(v)) out.push(v);
  }
  return out;
}

const redondeos = (b: number) => [b, Math.round(b), Math.round(b * 10) / 10, Math.round(b * 100) / 100];

/** ¿Hay un dato igual (o redondeado) entre los permitidos? */
function enDatos(v: number, permitidos: Set<number>): boolean {
  for (const c of permitidos) {
    if (redondeos(c).includes(v)) return true;
    if (c > 0 && c <= 1 && redondeos(c * 100).includes(v)) return true;   // 0,53 se escribe 53%
    if (c >= 1000 && redondeos(c / 1000).includes(v)) return true;        // 160000 se escribe «160 mil»
  }
  return false;
}

/** Un número pegado a una unidad (casos, pruebas, camas, mm, %, °C…) afirma una cantidad: tiene que estar en los datos. */
const UNIDAD = /^\s*(%|°|º|mm\b|casos?\b|pruebas?\b|camas?\b|habitantes\b|personas?\b|brigadas?\b|distritos?\b|soles\b|fallecid\w*|muertes?\b|hospitales\b|establecimientos\b|unidades\b|viviendas?\b|familias?\b|ni[nñ]os\b|menores\b|mil\b|millones\b)/i;
const ANTES_MONEDA = /(S\/|\$)\s*$/;

function conocido(v: number, permitidos: Set<number>, conUnidad: boolean): boolean {
  if (enDatos(v, permitidos)) return true;
  if (conUnidad) return false;                                         // «50 pruebas» no se acepta por ser un número «redondo»
  if (Number.isInteger(v) && v >= 0 && v <= 12) return true;          // conteos pequeños, listas, meses, semanas
  if (Number.isInteger(v) && v >= 2015 && v <= 2030) return true;     // años
  if (PERCENTILES_Y_UMBRALES.has(v)) return true;                    // P10, P90, percentil 99, semáforo 60/30
  return false;
}

/** Números del texto, indicando si van pegados a una unidad o a una moneda. */
export function numerosConUnidad(texto: string): { v: number; conUnidad: boolean }[] {
  const out: { v: number; conUnidad: boolean }[] = [];
  for (const m of texto.matchAll(NUMERO)) {
    const t = m[0].replace(/ /g, "");
    const v = /^\d{1,3}([.,]\d{3})+$/.test(t) ? Number(t.replace(/[.,]/g, "")) : Number(t.replace(",", "."));
    if (!Number.isFinite(v)) continue;
    const idx = m.index ?? 0;
    out.push({ v, conUnidad: UNIDAD.test(texto.slice(idx + m[0].length, idx + m[0].length + 18)) || ANTES_MONEDA.test(texto.slice(Math.max(0, idx - 4), idx)) });
  }
  return out;
}

export function numerosPermitidos(...textos: string[]): Set<number> {
  const s = new Set<number>();
  for (const t of textos) for (const m of t.match(/\d+(?:[.,]\d+)?/g) ?? []) s.add(Number(m.replace(",", ".")));
  return s;
}

const PROHIBIDO_EN_RESPUESTA =
  /(https?:|www\.|@\w+\.\w+|```|<\/?[a-z][^>]*>|\b(paracetamol|ibuprofeno|aspirina|naproxeno|diclofenaco|antibiotic\w*|amoxicilina|ivermectina|cloroquina|dosis|miligramos?|mg)\b)/i;

export type Salida = { ok: true; texto: string } | { ok: false; motivo: "vacia" | "fuera_de_tema" | "contenido" | "cifras"; detalle?: string };

export function revisarRespuesta(raw: unknown, permitidos: Set<number>): Salida {
  const texto = typeof raw === "string" ? raw.trim() : "";
  if (texto.length < 5) return { ok: false, motivo: "vacia" };
  if (/FUERA_DE_TEMA/.test(texto)) return { ok: false, motivo: "fuera_de_tema" };
  if (PROHIBIDO_EN_RESPUESTA.test(texto)) return { ok: false, motivo: "contenido" };
  const raras = numerosConUnidad(texto).filter((n) => !conocido(n.v, permitidos, n.conUnidad)).map((n) => n.v);
  if (raras.length) return { ok: false, motivo: "cifras", detalle: raras.slice(0, 5).join(", ") };
  return { ok: true, texto };
}
