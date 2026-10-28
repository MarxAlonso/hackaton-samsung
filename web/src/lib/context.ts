// Contexto que acompaña a la predicción: cifras oficiales 2026, establecimientos que notifican y reportes ciudadanos.
import { fmt } from "./data";
import { icon } from "./icons";
import { acc, accSummary, helpBtn } from "./ui";

export interface Establecimientos {
  meta: { fuente: string; desde_semana_epi: string; hasta_semana_epi: string; hasta: string; nota: string };
  distritos: Record<string, {
    casos_ultimas_8_semanas: number; casos_8_semanas_previas: number; establecimientos_que_notifican: number;
    top: { nombre: string; casos: number; pct: number; casos_previas: number; casos_anio: number }[];
  }>;
}
export type Reportes = Record<string, { criaderos: number; fiebre: number }>;

let estabCache: Promise<Establecimientos> | null = null;
export function loadEstablecimientos() {
  estabCache ??= fetch("/data/establecimientos.json").then((r) => {
    if (!r.ok) throw new Error("sin establecimientos");
    return r.json() as Promise<Establecimientos>;
  });
  return estabCache;
}

/** Reportes ciudadanos de las últimas 2 semanas. Si falla (sin red, sin servicio), devuelve vacío: nunca rompe la página. */
export async function loadReportes(distrito?: string): Promise<Reportes> {
  try {
    const r = await fetch(`/api/reportes${distrito ? `?d=${distrito}` : ""}`);
    if (!r.ok) return {};
    return ((await r.json()) as { distritos: Reportes }).distritos ?? {};
  } catch {
    return {};
  }
}

const sign = (v: number) => (v > 0 ? "+" : "") + fmt(v);

/** Tarjeta con las cifras oficiales de 2026 y la advertencia sobre lo que el modelo de hoy puede subestimar. */
export function renderOfficialContext(el: HTMLElement, ctx: any, sesgo: Record<string, number> | undefined, cdc?: any, names: Record<string, string> = {}, ajuste?: any) {
  const nac = ctx.nacional_se40;
  const se = cdc?.meta?.semana_epidemiologica;
  // Con el informe del CDC por distrito (más reciente) se usan sus totales; si no, los de la nota transcrita
  const deps: [string, { c26: number; c25: number; ult?: number }][] = cdc
    ? ["Tumbes", "Piura", "Lambayeque"].map((d) => [d, { c26: cdc.departamentos[d].casos_2026, c25: cdc.departamentos[d].casos_2025, ult: cdc.departamentos[d].casos_ultima_semana }])
    : Object.entries(ctx.dengue_departamentos.departamentos as Record<string, any>).map(([d, v]) => [d, { c26: v.casos_2026, c25: v.casos_2025 }]);
  const pctVs = (a: number, b: number) => Math.round((a / Math.max(b, 1) - 1) * 100);
  const rows = deps
    .map(([name, d]) => `<li><strong>${name}</strong><span class="big">${fmt(d.c26)}</span><span class="small muted">casos de dengue · ${sign(pctVs(d.c26, d.c25))}% frente a 2025 (${fmt(d.c25)})${d.ult != null ? ` · ${fmt(d.ult)} en la última semana` : ""}</span></li>`)
    .join("");
  const topDistricts = cdc ? Object.entries(cdc.distritos as Record<string, any>).sort((a, b) => b[1].casos_2026 - a[1].casos_2026).slice(0, 6) : [];
  const bias = sesgo && sesgo["2023"] && sesgo["2024"]
    ? ` En 2023 y 2024, sin casos recientes, los casos reales fueron unas ${Math.round(sesgo["2023"])} y ${Math.round(sesgo["2024"])} veces lo que el modelo de solo clima había previsto.`
    : "";
  const piura = deps.find(([d]) => d === "Piura")![1], lam = deps.find(([d]) => d === "Lambayeque")![1];
  el.innerHTML = accSummary({
    title: "Contexto oficial 2026: lo que reporta el CDC este año",
    summary: `Piura ${fmt(piura.c26)} casos (${sign(pctVs(piura.c26, piura.c25))}% frente a 2025) · Lambayeque ${fmt(lam.c26)} (${sign(pctVs(lam.c26, lam.c25))}%) · el modelo de solo clima se ajusta con estas cifras`,
    icon: "alertTriangle",
    ayuda: "contexto_oficial",
  }) + `<div class="acc-body">
    <p class="small muted">Casos de dengue confirmados y probables ${se ? `del 1 de enero hasta la semana epidemiológica ${se} (informe del CDC por distrito)` : "del 1 de enero al 12 de septiembre (semana epidemiológica 36)"}. Alerta epidemiológica N.° ${ctx.alerta_epidemiologica.numero} del Minsa (${new Date(ctx.alerta_epidemiologica.fecha + "T12:00:00").toLocaleDateString("es-PE", { day: "numeric", month: "long" })}).</p>
    <ul class="official-grid">${rows}
      <li><strong>Todo el país</strong><span class="big">${fmt(nac.dengue_casos)}</span><span class="small muted">casos hasta la semana 40 · +${nac.dengue_variacion_pct}% · ${nac.dengue_fallecidos} fallecidos (${nac.dengue_fallecidos_menores} menores)</span></li>
    </ul>
    ${topDistricts.length ? `<p class="small"><strong>Distritos del piloto con más casos en 2026:</strong> ${topDistricts.map(([id, c]) => `${names[id] ?? id} ${fmt(c.casos_2026)}`).join(" · ")} ${helpBtn("casos_2026_cdc", "casos 2026 por distrito")}</p>` : ""}
    <p class="data-note warn">${icon("info", 18)}<span><strong>Cómo leer el ranking de hoy.</strong> Los casos oficiales del sistema llegan con meses de retraso, así que el modelo de hoy usa solo clima: ordena bien los distritos, pero tiende a quedarse corto en la intensidad de las epidemias grandes.${bias} ${ajuste?.por_departamento ? ` <strong>Ajuste aplicado hoy</strong> a los casos esperados, con el acumulado oficial del año: ${Object.entries(ajuste.por_departamento as Record<string, any>).map(([d, v]) => `${d} ×${v.factor.toFixed(1)}`).join(", ")} ${helpBtn("ajuste_acumulado", "ajuste con el acumulado oficial")}.` : ""} Úsalo para decidir dónde mirar primero, junto con estas cifras.</span></p>
    <p class="small muted">Fuentes: CDC Perú (sala situacional de dengue, informe semanal por distrito), nota de prensa del Minsa del 20/10/2026, ENFEN (comunicado 16-2026).</p>
  </div>`;
}

/** Establecimientos que más casos notifican en el distrito (solo Piura) y señal ciudadana sin verificar. */
export async function renderDistrictExtras(el: HTMLElement, districtId: string) {
  const [estab, reportes] = await Promise.all([loadEstablecimientos().catch(() => null), loadReportes(districtId)]);
  const e = estab?.distritos[districtId];
  const rep = reportes[districtId];
  let html = "";
  if (e) {
    const trend = e.casos_ultimas_8_semanas - e.casos_8_semanas_previas;
    const arrow = trend > 0 ? "sube" : trend < 0 ? "baja" : "se mantiene";
    html += acc({
      title: "Dónde se concentra la atención en este distrito",
      icon: "hospital",
      ayuda: "establecimientos",
      summary: `${fmt(e.casos_ultimas_8_semanas)} casos notificados en 8 semanas · ${e.establecimientos_que_notifican} establecimientos · ${arrow} frente a las 8 anteriores · mayor carga: ${e.top[0].nombre}`,
      body: `<p class="small muted">Casos de dengue notificados por establecimiento en las últimas 8 semanas (${estab!.meta.desde_semana_epi.replace("-SE", " SE ")} a ${estab!.meta.hasta_semana_epi.replace("-SE", " SE ")}, hasta el ${new Date(estab!.meta.hasta + "T12:00:00").toLocaleDateString("es-PE", { day: "numeric", month: "short" })}): ${fmt(e.casos_ultimas_8_semanas)} casos en ${e.establecimientos_que_notifican} establecimientos; frente a las 8 semanas previas ${arrow} (${fmt(e.casos_8_semanas_previas)}).</p>
      <ol class="estab">${e.top.map((t) => {
        const d = t.casos - t.casos_previas;
        return `<li><span class="estab-name">${t.nombre}</span>
          <span class="estab-bar" title="${t.pct}% de los casos del distrito"><i style="width:${Math.max(4, t.pct)}%"></i></span>
          <span class="num">${t.casos}</span>
          <span class="small ${d > 0 ? "up" : "muted"}">${d > 0 ? "▲" : d < 0 ? "▼" : "="} ${d === 0 ? "igual" : fmt(Math.abs(d))}</span></li>`;
      }).join("")}</ol>
      <p class="small muted">${estab!.meta.nota} Fuente: ${estab!.meta.fuente}.</p>`,
    });
  }
  if (rep && rep.criaderos + rep.fiebre > 0) {
    html += `<p class="data-note">${icon("users", 18)}<span><strong>Reportes ciudadanos (sin verificar), últimas 2 semanas:</strong> ${rep.criaderos} sobre criaderos de zancudos y ${rep.fiebre} sobre personas con fiebre. Son avisos anónimos de vecinos; hay que confirmarlos en campo y no alimentan el modelo.</span></p>`;
  }
  el.innerHTML = html;
}
