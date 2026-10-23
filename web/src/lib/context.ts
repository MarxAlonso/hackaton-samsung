// Contexto que acompaña a la predicción: cifras oficiales 2026, establecimientos que notifican y reportes ciudadanos.
import { fmt } from "./data";
import { icon } from "./icons";

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
export function renderOfficialContext(el: HTMLElement, ctx: any, sesgo: Record<string, number> | undefined) {
  const dep = ctx.dengue_departamentos, nac = ctx.nacional_se40;
  const rows = Object.entries(dep.departamentos as Record<string, any>)
    .map(([name, d]) => `<li><strong>${name}</strong><span class="big">${fmt(d.casos_2026)}</span><span class="small muted">casos de dengue · ${sign(Math.round(d.variacion_pct))}% frente a 2025 (${fmt(d.casos_2025)})</span></li>`)
    .join("");
  const bias = sesgo && sesgo["2023"] && sesgo["2024"]
    ? ` En 2023 y 2024, sin casos recientes, los casos reales fueron unas ${Math.round(sesgo["2023"])} y ${Math.round(sesgo["2024"])} veces lo que el modelo de solo clima había previsto.`
    : "";
  el.innerHTML = `
    <div class="official-head">
      <span class="ico-box brand">${icon("alertTriangle", 22)}</span>
      <div>
        <p class="eyebrow">Contexto oficial 2026</p>
        <h2>Lo que reporta el CDC este año</h2>
        <p class="small muted">Casos confirmados y probables del 1 de enero al 12 de septiembre (semana epidemiológica 36). Alerta epidemiológica N.° ${ctx.alerta_epidemiologica.numero} del Minsa (${new Date(ctx.alerta_epidemiologica.fecha + "T12:00:00").toLocaleDateString("es-PE", { day: "numeric", month: "long" })}).</p>
      </div>
    </div>
    <ul class="official-grid">${rows}
      <li><strong>Todo el país</strong><span class="big">${fmt(nac.dengue_casos)}</span><span class="small muted">casos hasta la semana 40 · +${nac.dengue_variacion_pct}% · ${nac.dengue_fallecidos} fallecidos (${nac.dengue_fallecidos_menores} menores)</span></li>
    </ul>
    <p class="data-note warn">${icon("info", 18)}<span><strong>Cómo leer el ranking de hoy.</strong> Los casos oficiales del sistema llegan con meses de retraso, así que el modelo de hoy usa solo clima: ordena bien los distritos, pero tiende a quedarse corto en la intensidad de las epidemias grandes.${bias} Úsalo para decidir dónde mirar primero, junto con estas cifras.</span></p>
    <p class="small muted">Fuentes: CDC Perú (informe de dengue al 12/09/2026 y sala situacional), nota de prensa del Minsa del 20/10/2026, ENFEN (comunicado 16-2026).</p>`;
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
    html += `<section class="extra card">
      <h3 class="inline-ico">${icon("hospital", 20)} Dónde se concentra la atención en este distrito</h3>
      <p class="small muted">Casos de dengue notificados por establecimiento en las últimas 8 semanas (${estab!.meta.desde_semana_epi.replace("-SE", " SE ")} a ${estab!.meta.hasta_semana_epi.replace("-SE", " SE ")}, hasta el ${new Date(estab!.meta.hasta + "T12:00:00").toLocaleDateString("es-PE", { day: "numeric", month: "short" })}): ${fmt(e.casos_ultimas_8_semanas)} casos en ${e.establecimientos_que_notifican} establecimientos; frente a las 8 semanas previas ${arrow} (${fmt(e.casos_8_semanas_previas)}).</p>
      <ol class="estab">${e.top.map((t) => {
        const d = t.casos - t.casos_previas;
        return `<li><span class="estab-name">${t.nombre}</span>
          <span class="estab-bar" title="${t.pct}% de los casos del distrito"><i style="width:${Math.max(4, t.pct)}%"></i></span>
          <span class="num">${t.casos}</span>
          <span class="small ${d > 0 ? "up" : "muted"}">${d > 0 ? "▲" : d < 0 ? "▼" : "="} ${d === 0 ? "igual" : fmt(Math.abs(d))}</span></li>`;
      }).join("")}</ol>
      <p class="small muted">${estab!.meta.nota} Fuente: ${estab!.meta.fuente}.</p>
    </section>`;
  }
  if (rep && rep.criaderos + rep.fiebre > 0) {
    html += `<p class="data-note">${icon("users", 18)}<span><strong>Reportes ciudadanos (sin verificar), últimas 2 semanas:</strong> ${rep.criaderos} sobre criaderos de zancudos y ${rep.fiebre} sobre personas con fiebre. Son avisos anónimos de vecinos; hay que confirmarlos en campo y no alimentan el modelo.</span></p>`;
  }
  el.innerHTML = html;
}
