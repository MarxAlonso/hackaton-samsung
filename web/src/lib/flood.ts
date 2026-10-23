// Gráfico de lluvias extremas: lluvia diaria (barras), acumulado de 3 días (línea) y los dos
// umbrales del distrito. Todo en milímetros (un solo eje). Lo observado va sólido; el pronóstico, punteado.
import { fmt, weekLabel } from "./data";

export interface FloodSeries { fechas: string[]; mm: number[]; r3: (number | null)[]; n_obs: number }
export interface FloodInfo {
  nivel: "alto" | "medio" | "bajo";
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

const W = 920, H = 270;
const M = { top: 30, right: 118, bottom: 30, left: 50 };
const DAY = 864e5;

export function renderFlood(el: HTMLElement, s: FloodSeries, f: FloodInfo) {
  const t = s.fechas.map((d) => new Date(d + "T12:00:00").getTime());
  const t0 = t[0], t1 = t[t.length - 1];
  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  const peakR3 = Math.max(...s.r3.map((v) => v ?? 0), 1);
  const yMax = Math.ceil(Math.max(f.umbral_alto_mm * 1.15, peakR3 * 1.12, 10) / 10) * 10;
  const x = (ms: number) => M.left + ((ms - t0) / Math.max(t1 - t0, DAY)) * iw;
  const y = (v: number) => M.top + ih - (v / yMax) * ih;
  const bw = Math.max(5, (iw / Math.max(t.length, 1)) * 0.62);
  const ticks = [0, 0.5, 1].map((k) => k * yMax);

  // tramo sin datos (rezago del reanálisis entre lo observado y el pronóstico)
  const lastObs = t[s.n_obs - 1], firstFc = t[s.n_obs];
  const gap = s.n_obs < t.length && firstFc - lastObs > 2 * DAY ? { a: x(lastObs + DAY / 2), b: x(firstFc - DAY / 2), days: Math.round((firstFc - lastObs) / DAY) - 1 } : null;

  const linePath = (from: number, to: number) => {
    let d = "", pen = false;
    for (let i = from; i < to; i++) {
      const v = s.r3[i];
      if (v == null) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${x(t[i]).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const peakIdx = s.fechas.indexOf(f.fecha_max);
  const peakX = peakIdx >= 0 ? x(t[peakIdx]) : null;
  const levelColor = f.nivel === "alto" ? "var(--critical)" : f.nivel === "medio" ? "var(--warning)" : "var(--series-1)";

  el.innerHTML = `
  <div class="chart-wrap">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Lluvia diaria y acumulada de 3 días frente a los umbrales de lluvia extrema">
      ${ticks.map((v) => `<line x1="${M.left}" x2="${W - M.right}" y1="${y(v)}" y2="${y(v)}" stroke="var(--border)"/>
        <text x="${M.left - 8}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="var(--text-3)">${fmt(v)}</text>`).join("")}
      <text x="${M.left}" y="${M.top - 14}" font-size="11" fill="var(--text-3)">mm</text>
      ${gap ? `<rect x="${gap.a}" y="${M.top}" width="${gap.b - gap.a}" height="${ih}" fill="var(--surface-2)"/>
        <text x="${(gap.a + gap.b) / 2}" y="${M.top + 14}" font-size="10.5" text-anchor="middle" fill="var(--text-3)">${gap.days} días sin dato</text>` : ""}
      <line x1="${M.left}" x2="${W - M.right}" y1="${y(f.umbral_medio_mm)}" y2="${y(f.umbral_medio_mm)}" stroke="var(--warning)" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${W - M.right + 6}" y="${y(f.umbral_medio_mm) + 4}" font-size="11" fill="var(--warning-ink)">Intensa ${fmt(f.umbral_medio_mm)} mm</text>
      <line x1="${M.left}" x2="${W - M.right}" y1="${y(f.umbral_alto_mm)}" y2="${y(f.umbral_alto_mm)}" stroke="var(--critical)" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${W - M.right + 6}" y="${y(f.umbral_alto_mm) + 4}" font-size="11" fill="var(--critical-ink)">Extrema ${fmt(f.umbral_alto_mm)} mm</text>
      ${s.mm.map((v, i) => {
        const fc = i >= s.n_obs;
        const h = (v / yMax) * ih;
        return `<rect x="${(x(t[i]) - bw / 2).toFixed(1)}" y="${(M.top + ih - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" rx="1.5"
          fill="${fc ? "none" : "var(--rain)"}" ${fc ? `stroke="var(--series-1)" stroke-width="1.3" stroke-dasharray="3 2"` : ""}/>`;
      }).join("")}
      <path d="${linePath(0, s.n_obs)}" fill="none" stroke="var(--series-1)" stroke-width="2.4" stroke-linejoin="round"/>
      <path d="${linePath(s.n_obs, t.length)}" fill="none" stroke="var(--series-1)" stroke-width="2.4" stroke-dasharray="6 4" stroke-linejoin="round"/>
      ${peakX != null ? `<circle cx="${peakX}" cy="${y(f.lluvia_max_3d_mm)}" r="5.5" fill="none" stroke="${levelColor}" stroke-width="2.4"/>
        <text x="${peakX > W - 260 ? peakX - 10 : peakX + 10}" y="${y(f.lluvia_max_3d_mm) - 10}" font-size="12" font-weight="700" text-anchor="${peakX > W - 260 ? "end" : "start"}" fill="var(--text)">Máx. 3 días: ${fmt(f.lluvia_max_3d_mm)} mm</text>
        <text x="${peakX > W - 260 ? peakX - 10 : peakX + 10}" y="${y(f.lluvia_max_3d_mm) + 4}" font-size="11" text-anchor="${peakX > W - 260 ? "end" : "start"}" fill="var(--text-2)">${weekLabel(f.fecha_max, false)}${f.es_pronostico ? " (pronóstico)" : ""} · ${f.ratio_umbral_alto.toFixed(1)}× umbral extremo</text>` : ""}
      <text x="${M.left}" y="${H - 8}" font-size="11" fill="var(--text-3)">${weekLabel(s.fechas[0], false)}</text>
      <text x="${W - M.right}" y="${H - 8}" font-size="11" text-anchor="end" fill="var(--text-3)">${weekLabel(s.fechas[s.fechas.length - 1], false)}</text>
      <line class="xhair" x1="0" x2="0" y1="${M.top}" y2="${M.top + ih}" stroke="var(--text-3)" visibility="hidden"/>
      <rect class="hit" x="${M.left}" y="${M.top}" width="${iw}" height="${ih}" fill="transparent"/>
    </svg>
    <div class="chart-tooltip" hidden></div>
  </div>
  <div class="legend">
    <span><i class="box" style="background:var(--rain)"></i>Lluvia diaria observada</span>
    <span><i class="box" style="border:1.3px dashed var(--series-1);background:none"></i>Lluvia diaria pronosticada</span>
    <span><i style="background:var(--series-1)"></i>Acumulado de 3 días</span>
    <span><i style="background:var(--warning)"></i>Umbral de lluvia intensa (percentil 99)</span>
    <span><i style="background:var(--critical)"></i>Umbral de lluvia extrema (percentil 99,9)</span>
  </div>`;

  const svg = el.querySelector("svg")!, tip = el.querySelector<HTMLDivElement>(".chart-tooltip")!;
  const xhair = svg.querySelector<SVGLineElement>(".xhair")!, hit = svg.querySelector<SVGRectElement>(".hit")!;
  hit.addEventListener("mousemove", (ev) => {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    let best = 0;
    for (let i = 1; i < t.length; i++) if (Math.abs(x(t[i]) - px) < Math.abs(x(t[best]) - px)) best = i;
    xhair.setAttribute("x1", String(x(t[best]))); xhair.setAttribute("x2", String(x(t[best]))); xhair.setAttribute("visibility", "visible");
    const fc = best >= s.n_obs, r3 = s.r3[best];
    tip.hidden = false;
    tip.innerHTML = `<strong>${weekLabel(s.fechas[best])}</strong>${fc ? " · pronóstico" : ""}<br>Lluvia del día: ${fmt(s.mm[best])} mm<br>Acumulado 3 días: ${r3 == null ? "—" : fmt(r3) + " mm"}`;
    const lx = (x(t[best]) / W) * r.width;
    tip.style.left = `${lx > r.width - 230 ? lx - 220 : lx + 14}px`; tip.style.top = "10px";
  });
  hit.addEventListener("mouseleave", () => { tip.hidden = true; xhair.setAttribute("visibility", "hidden"); });
}

/** Frase de resumen para autoridad e informe. `despues` es el texto sobre las consecuencias sanitarias. */
export function floodSentence(f: FloodInfo, despues: string) {
  const when = `${weekLabel(f.fecha_max, false)}${f.es_pronostico ? " (pronóstico)" : ""}`;
  if (f.nivel === "bajo") {
    return `El máximo acumulado en 3 días es ${fmt(f.lluvia_max_3d_mm)} mm (${when}), el ${Math.round((100 * f.lluvia_max_3d_mm) / f.umbral_alto_mm)}% del umbral extremo de este distrito (${fmt(f.umbral_alto_mm)} mm). No se espera lluvia extrema.`;
  }
  return `${f.es_pronostico ? "Se pronostican" : "Se registraron"} <strong>${fmt(f.lluvia_max_3d_mm)} mm en 3 días</strong> hacia el ${when}: ` +
    `${f.nivel === "alto" ? "comparable a los eventos del Niño costero de 2017 y 2023 en este distrito" : "lluvia intensa, con encharcamientos probables"} ` +
    `(umbral intenso ${fmt(f.umbral_medio_mm)} mm, extremo ${fmt(f.umbral_alto_mm)} mm). ${despues}`;
}
