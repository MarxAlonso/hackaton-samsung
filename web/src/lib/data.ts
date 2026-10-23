// Tipos y carga de los archivos que exporta el pipeline de Python (ml/src/export.py)

export type Nivel = "alto" | "medio" | "bajo";
/** "casos" = modelo que usa casos recientes; "clima" = solo clima (hoy, cuando el último caso oficial es antiguo). */
export type ModeloTipo = "casos" | "clima";
export type DiseaseKey = "dengue" | "leptospirosis" | "eda" | "golpe_calor" | "ira";

export interface District {
  district_id: string;
  district: string;
  province: string;
  department: string;
  lat: number;
  lon: number;
  altitude: number;
  population: number;
  water_access: number;
}

export interface Risk {
  prob: number;
  nivel: Nivel;
  casos_p10?: number;
  casos_p50?: number;
  casos_p90?: number;
  confianza?: "alta" | "media" | "baja";
  confianza_score?: number;
}

export interface FloodInfoData {
  nivel: Nivel;
  lluvia_max_3d_mm: number;
  fecha_max: string;
  es_pronostico: boolean;
  umbral_medio_mm: number;
  umbral_alto_mm: number;
  ratio_umbral_alto: number;
  lluvia_14d_mm: number;
  lluvia_pronostico_16d_mm: number | null;
  con_pronostico: boolean;
}

export interface DistrictPrediction {
  district_id: string;
  modelo_tipo: ModeloTipo;
  ultimo_dato_casos: string;
  /** Solo en los replays: lo que realmente pasó en las 4 semanas siguientes (casos reales del CDC-MINSA). */
  real?: { casos_4_semanas: number; brote: boolean };
  inundacion: FloodInfoData;
  features: Record<string, number>;
  riesgos: Record<DiseaseKey, Risk>;
  nivel: Nivel;
  top_riesgos: DiseaseKey[];
  recursos: { pruebas: number; camas: number };
  clima: { lluvia_ultimas_2sem: number; lluvia_2_a_6sem: number; tmax: number; tmedia: number };
}

export interface Scenario {
  etiqueta: string;
  semana: string;
  nino12: number;
  oni: number;
  modelo: { id: "prod" | "eval"; origen: string; entrenado_hasta: string; familia: ModeloTipo; distritos_con_casos_recientes: number };
  tasa_base: Record<ModeloTipo, Record<string, number>>;
  ventana_lluvia: { hasta: string; con_pronostico: boolean };
  inundacion_serie: Record<string, { fechas: string[]; mm: number[]; r3: (number | null)[]; n_obs: number }>;
  distritos: DistrictPrediction[];
}

export interface SimpleModel {
  features: string[];
  mean: number[];
  scale: number[];
  coef: number[];
  intercept: number;
}

export interface AppData {
  generado: string;
  horizonte_semanas: number;
  distritos: District[];
  escenarios: Record<"actual" | "2023" | "2017", Scenario>;
  referencia_2023: Record<string, Record<string, number>>;
  pronostico: Record<string, { lluvia_16d: number; tmax_16d: number; desde: string; hasta: string }>;
  modelo: {
    features: Record<ModeloTipo, string[]>;
    dengue_features: string[];
    rain_features: string[];
    temp_features: string[];
    simple_features: Record<ModeloTipo, string[]>;
    simples: Record<ModeloTipo, Record<string, SimpleModel>>;
    umbrales_nivel: { alto: number; medio: number };
  };
  datos: {
    cobertura: Record<string, { fuente: string; hasta: string; desde?: string; anio_provisional_descartado?: number | null; casos_total?: number }>;
    licencia: string;
    cita: string;
    ultimo_caso_oficial: string;
  };
  metricas: any;
  monitoreo: any;
  reentrenamiento: any;
  lluvias_extremas: { metodo: string; dias_distrito_sobre_umbral_alto_por_anio: Record<string, number>; umbrales_mm: Record<string, { medio: number; alto: number }> };
  contenido: {
    lluvia_extrema: { info: { nombre: string; icono: string; causa: string; despues: string }; ciudadano: Record<Nivel, string[]>; autoridad: Record<Nivel, string[]> };
    enfermedades: Record<DiseaseKey, { nombre: string; icono: string; causa: string; sintomas: string; senal_alarma: string; relacionadas: string }>;
    ciudadano: Record<DiseaseKey, string[]>;
    autoridad: Record<DiseaseKey, Record<Nivel, string[]>>;
    niveles: Record<Nivel, { label: string; color: string }>;
  };
}

/** Serie semanal completa (2015 → hoy) por distrito. Se carga solo en el panel de autoridad. */
export interface SeriesData {
  semanas: string[];
  /** dengue, inc y gore usan NaN donde el dato es desconocido (el archivo trae null). */
  distritos: Record<string, { dengue: number[]; inc: number[]; canal: number[]; lluvia: number[]; tmax: number[]; gore: number[] | null }>;
}

let cache: Promise<AppData> | null = null;
export function loadData(): Promise<AppData> {
  cache ??= fetch("/data/app.json").then((r) => {
    if (!r.ok) throw new Error("No se pudo cargar app.json");
    return r.json();
  });
  return cache;
}

let seriesCache: Promise<SeriesData> | null = null;
export function loadSeries(): Promise<SeriesData> {
  seriesCache ??= fetch("/data/series.json").then(async (r) => {
    if (!r.ok) throw new Error("No se pudo cargar series.json");
    const data = await r.json();
    // null = sin dato oficial: se convierte en NaN para que ningún gráfico lo confunda con cero
    const nan = (a: (number | null)[] | null) => (a ? a.map((v) => (v === null ? NaN : v)) : null);
    for (const d of Object.values<any>(data.distritos)) {
      d.dengue = nan(d.dengue);
      d.inc = nan(d.inc);
      d.gore = nan(d.gore);
    }
    return data as SeriesData;
  });
  return seriesCache;
}

export const NIVEL_LABEL: Record<Nivel, string> = { alto: "Riesgo alto", medio: "Riesgo medio", bajo: "Riesgo bajo" };
export const NIVEL_ORDER: Record<Nivel, number> = { alto: 2, medio: 1, bajo: 0 };

export function levelOf(prob: number, t: { alto: number; medio: number }): Nivel {
  return prob >= t.alto ? "alto" : prob >= t.medio ? "medio" : "bajo";
}

export const pct = (p: number) => (p > 0.99 ? ">99%" : p < 0.01 ? "<1%" : `${Math.round(p * 100)}%`);
export const fmt = (n: number) => Math.round(n).toLocaleString("es-PE");

export function badge(nivel: Nivel, text = NIVEL_LABEL[nivel]) {
  return `<span class="badge lvl-${nivel}">${text}</span>`;
}

export function fillTemplate(text: string, recursos: { pruebas: number; camas: number }) {
  return text.replace("{tests}", fmt(recursos.pruebas)).replace("{beds}", fmt(recursos.camas));
}

export function weekLabel(iso: string, withYear = true) {
  return new Date(iso + "T12:00:00").toLocaleDateString("es-PE", withYear
    ? { day: "numeric", month: "short", year: "numeric" }
    : { day: "numeric", month: "short" });
}

export function monthLabel(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString("es-PE", { month: "short", year: "2-digit" });
}
