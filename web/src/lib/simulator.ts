// Simulador "¿y si llueve más?": corre los modelos ONNX de dengue en el navegador.
// Misma lógica que api/scoring.py → apply_scenario().
import type { AppData, DiseaseKey, DistrictPrediction, ModeloTipo, Risk } from "./data";
import { levelOf } from "./data";

type Ort = typeof import("onnxruntime-web");
let ortPromise: Promise<Ort> | null = null;
const sessions: Record<string, Promise<import("onnxruntime-web").InferenceSession>> = {};
const ORT_VERSION = "1.30.0";

const ORT_CDN = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VERSION}/dist/`;

// Se carga desde el CDN y no se empaqueta: el .wasm (~27 MB) supera el límite de 25 MiB
// por archivo de Cloudflare Workers. Solo se descarga cuando alguien usa el simulador.
async function getOrt(): Promise<Ort> {
  ortPromise ??= (import(/* @vite-ignore */ `${ORT_CDN}ort.wasm.min.mjs`) as Promise<Ort>).then((ort) => {
    ort.env.wasm.wasmPaths = ORT_CDN;
    ort.env.wasm.numThreads = 1;
    return ort;
  });
  return ortPromise;
}

async function session(name: string) {
  const ort = await getOrt();
  sessions[name] ??= ort.InferenceSession.create(`/models/${name}.onnx`);
  return sessions[name];
}

/** Nombre del archivo ONNX: "prod_" = modelo de producción (hoy); "clima_" = familia solo clima. */
const modelName = (id: "prod" | "eval", tipo: ModeloTipo, base: string) => `${id === "prod" ? "prod_" : ""}${tipo === "clima" ? "clima_" : ""}${base}`;

export interface ScenarioInput {
  lluviaPct: number; // 0 = clima observado; 100 = lluvias como el pico de 2023
  tempDelta: number; // °C
}

export function applyScenario(app: AppData, pred: DistrictPrediction, input: ScenarioInput) {
  const ref = app.referencia_2023[pred.district_id];
  const f = { ...pred.features };
  const k = input.lluviaPct / 100;
  for (const name of app.modelo.rain_features) f[name] = Math.max(0, f[name] + k * (ref[name] - pred.features[name]));
  for (const name of app.modelo.temp_features) f[name] = f[name] + input.tempDelta;
  return f;
}

function confidence(p10: number, p50: number, p90: number, prob: number, tipo: ModeloTipo) {
  const spread = (p90 - p10) / (p50 + 10);
  let score = 0.6 * Math.abs(prob - 0.5) * 2 + 0.4 * Math.max(0, 1 - spread / 3);
  let label: Risk["confianza"] = score >= 0.6 ? "alta" : score >= 0.35 ? "media" : "baja";
  // Sin casos recientes ("clima") nunca pasa de media: ordena bien los distritos pero calcula mal cuántos casos habrá
  if (tipo === "clima") { label = label === "baja" ? "baja" : "media"; score = Math.min(score, 0.5); }
  return { label, score };
}

export async function simulate(app: AppData, pred: DistrictPrediction, input: ScenarioInput, modelId: "prod" | "eval" = "eval") {
  const ort = await getOrt();
  const f = applyScenario(app, pred, input);
  const tipo = pred.modelo_tipo;
  const vector = Float32Array.from(app.modelo.features[tipo].map((n) => f[n]));
  const tensor = new ort.Tensor("float32", vector, [1, vector.length]);

  const clf = await session(modelName(modelId, tipo, "dengue_outbreak"));
  const clfOut = await clf.run({ features: tensor });
  const probs = clfOut[clf.outputNames[1]].data as Float32Array; // [p(no brote), p(brote)]
  const prob = probs[1];

  const q: Record<string, number> = {};
  for (const name of ["p10", "p50", "p90"]) {
    const s = await session(modelName(modelId, tipo, `dengue_cases_${name}`));
    const out = await s.run({ features: tensor });
    q[name] = Math.max(0, Math.expm1((out[s.outputNames[0]].data as Float32Array)[0]));
  }
  [q.p10, q.p50, q.p90] = [q.p10, q.p50, q.p90].sort((a, b) => a - b); // P10 ≤ P50 ≤ P90, como en Python
  const conf = confidence(q.p10, q.p50, q.p90, prob, tipo);
  const t = app.modelo.umbrales_nivel;
  const riesgos = {
    dengue: {
      prob, nivel: levelOf(prob, t), casos_p10: Math.round(q.p10), casos_p50: Math.round(q.p50),
      casos_p90: Math.round(q.p90), confianza: conf.label, confianza_score: conf.score,
    },
  } as Record<DiseaseKey, Risk>;

  for (const [disease, m] of Object.entries(app.modelo.simples[tipo])) {
    const values = m.features.map((name) => (name === "own_inc_0_3" ? f[`${disease}_inc_0_3`] : f[name]));
    if (values.some((v) => v === undefined || Number.isNaN(v))) continue; // falta un dato: no se estima
    const z = m.intercept + values.reduce((a, v, i) => a + (m.coef[i] * (v - m.mean[i])) / m.scale[i], 0);
    const p = 1 / (1 + Math.exp(-z));
    riesgos[disease as DiseaseKey] = { prob: p, nivel: levelOf(p, t) };
  }
  return {
    riesgos,
    recursos: { pruebas: Math.ceil(q.p90 * 1.5), camas: Math.ceil(q.p90 * 0.04) },
    lluvia_2_a_6sem: f.rain_2_6,
  };
}
