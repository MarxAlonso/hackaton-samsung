// Prueba de humo del sitio publicado: páginas, datos y modelos. Solo usa fetch (Node 20+).
// Uso: node scripts/smoke.mjs [https://alerta-salud-nino.marxchip99.workers.dev]
const BASE = (process.argv[2] ?? "https://alerta-salud-nino.marxchip99.workers.dev").replace(/\/$/, "");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fails = 0;

async function get(path, tries = 4) {
  for (let i = 1; ; i++) {
    try {
      const r = await fetch(BASE + path, { redirect: "follow" });
      if (r.ok || i >= tries) return r;
    } catch (e) {
      if (i >= tries) throw e;
    }
    await wait(2000 * i); // el despliegue puede tardar unos segundos en propagarse
  }
}

async function check(name, fn) {
  try {
    const detail = await fn();
    console.log(`OK     ${name}${detail ? " — " + detail : ""}`);
  } catch (e) {
    fails++;
    console.log(`FALLA  ${name} — ${e.message}`);
  }
}
const must = (cond, msg) => { if (!cond) throw new Error(msg); };

const PAGES = {
  "/": "Alerta Salud",
  "/ciudadano/": "Soy ciudadano",
  "/autoridad/": "Panel de priorización",
  "/plan/": "Plan de acción",
  "/modelo/": "Cómo funciona el modelo",
  "/construccion/": "Cómo se construyó",
  "/demo/": "Demo guiada",
  "/offline/": "sin conexión",
};
for (const [path, text] of Object.entries(PAGES)) {
  await check(`página ${path}`, async () => {
    const r = await get(path);
    must(r.ok, `HTTP ${r.status}`);
    const html = await r.text();
    must(html.toLowerCase().includes(text.toLowerCase()), `no contiene "${text}"`);
    return `${Math.round(html.length / 1024)} KB`;
  });
}

let app;
await check("app.json válido y sin NaN", async () => {
  const r = await get("/data/app.json");
  must(r.ok, `HTTP ${r.status}`);
  const raw = await r.text();
  must(!/\bNaN\b|\bInfinity\b/.test(raw), "contiene NaN o Infinity");
  app = JSON.parse(raw);
  must(app.distritos.length === 47, `distritos: ${app.distritos.length}`);
  for (const k of ["actual", "2023", "2017"]) must(app.escenarios[k]?.distritos?.length === 47, `escenario ${k} incompleto`);
  return `generado ${app.generado}, ${app.distritos.length} distritos`;
});

await check("datos oficiales con fecha y licencia", async () => {
  must(app.datos.ultimo_caso_oficial, "falta ultimo_caso_oficial");
  must(/ODC|Open Data/i.test(app.datos.licencia), "falta licencia ODC-By");
  return `último caso oficial ${app.datos.ultimo_caso_oficial}`;
});

await check("probabilidades dentro de [0, 1] y rangos ordenados", async () => {
  for (const [k, esc] of Object.entries(app.escenarios)) {
    for (const d of esc.distritos) {
      const r = d.riesgos.dengue;
      must(r.prob >= 0 && r.prob <= 1, `${k}/${d.district_id}: prob ${r.prob}`);
      must(r.casos_p10 <= r.casos_p50 && r.casos_p50 <= r.casos_p90, `${k}/${d.district_id}: rango desordenado`);
    }
  }
});

await check("series.json válido", async () => {
  const r = await get("/data/series.json");
  must(r.ok, `HTTP ${r.status}`);
  const s = JSON.parse(await r.text());
  must(Object.keys(s.distritos).length === 47, "faltan distritos");
  return `${Math.round((await (await get("/data/series.json")).text()).length / 1024)} KB`;
});

const MODELS = ["dengue_outbreak", "dengue_cases_p10", "dengue_cases_p50", "dengue_cases_p90"];
const names = ["", "prod_", "clima_", "prod_clima_"].flatMap((p) => MODELS.map((m) => `${p}${m}`));
await check(`${names.length} modelos ONNX disponibles`, async () => {
  for (const n of names) {
    const r = await get(`/models/${n}.onnx`);
    must(r.ok, `${n}: HTTP ${r.status}`);
    must((await r.arrayBuffer()).byteLength > 1000, `${n}: vacío`);
  }
});

await check("PWA: manifest y service worker", async () => {
  const m = await get("/manifest.webmanifest");
  must(m.ok && (await m.json()).name, "manifest inválido");
  const sw = await get("/sw.js");
  must(sw.ok, "sw.js no responde");
  must((await sw.text()).includes("PRECACHE_URLS"), "sw.js sin lista de caché");
});

await check("IA: /api/explicar responde en español", async () => {
  const r = await fetch(BASE + "/api/explicar", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ modo: "ciudadano", contexto: { distrito: "Castilla", dengue: "medio" }, respaldo: "respaldo" }),
  });
  must(r.ok, `HTTP ${r.status}`);
  const j = await r.json();
  must(typeof j.texto === "string" && j.texto.length > 20, "respuesta vacía");
  return `fuente: ${j.fuente}`;
});

console.log(fails ? `\n${fails} prueba(s) fallaron` : "\nTodas las pruebas de humo pasaron");
process.exit(fails ? 1 : 0);
