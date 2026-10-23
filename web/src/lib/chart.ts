// Gráfico de historia del dengue en SVG puro: casos semanales vs umbral de brote (canal
// endémico), semanas en brote marcadas, picos anotados y la banda del pronóstico.
// La lluvia va en un gráfico aparte con su propio eje (nunca doble eje).
import type { Risk, SeriesData } from "./data";
import { fmt, weekLabel } from "./data";

export const W = 920;
const H = 340;
const M = { top: 34, right: 16, bottom: 28, left: 52 };
const RAIN_H = 90;

export function niceMax(v: number) {
  if (v <= 5) return 5;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}

export function linePath(xs: number[], ys: number[]) {
  return xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join("");
}

/** Picos: máximos locales sobre el umbral, separados al menos `gap` semanas. */
export function findPeaks(values: number[], canal: number[], gap = 8, max = 3) {
  const cand: number[] = [];
  for (let i = 1; i < values.length - 1; i++) {
    if (values[i] >= values[i - 1] && values[i] > values[i + 1] && values[i] > canal[i] && values[i] >= 5) cand.push(i);
  }
  cand.sort((a, b) => values[b] - values[a]);
  const out: number[] = [];
  for (const i of cand) {
    if (out.every((j) => Math.abs(j - i) >= gap)) out.push(i);
    if (out.length >= max) break;
  }
  return out.sort((a, b) => a - b);
}

export interface HistoryOpts {
  baseWeek: string;      // última semana observada del escenario
  horizon: number;       // semanas de pronóstico
  risk: Risk;            // P10/P50/P90 a 4 semanas
  weeksBack: number;     // ventana hacia atrás
  showActual: boolean;   // en replay, dibujar también lo que realmente pasó
}

export interface HistorySummary {
  ventana: { desde: string; hasta: string; semanas: number };
  picos: { semana: string; casos: number; veces_umbral: number }[];
  semanas_en_brote: number;
  ultimas_8_semanas: { semana: string; casos: number; umbral: number; lluvia_mm: number }[];
  pronostico_4_semanas: { p10: number; p50: number; p90: number; por_semana_p50: number };
  tendencia: "subiendo" | "bajando" | "estable";
  lo_que_paso?: { casos_reales_4_semanas: number; dentro_del_rango: boolean };
}

export function renderHistory(el: HTMLElement, series: SeriesData, districtId: string, o: HistoryOpts): HistorySummary {
  const s = series.distritos[districtId];
  const all = series.semanas;
  const baseIdx = all.indexOf(o.baseWeek);
  const start = Math.max(0, baseIdx - o.weeksBack + 1);
  const endObs = o.showActual ? Math.min(all.length - 1, baseIdx + o.horizon) : baseIdx;
  const weeks = all.slice(start, endObs + 1);
  const cases = s.dengue.slice(start, endObs + 1);
  const canal = s.canal.slice(start, endObs + 1);
  const rain = s.lluvia.slice(start, endObs + 1);
  const nCols = Math.max(weeks.length, baseIdx - start + 1 + o.horizon);
  const bi = baseIdx - start;

  const per = { lo: (o.risk.casos_p10 ?? 0) / o.horizon, mid: (o.risk.casos_p50 ?? 0) / o.horizon, hi: (o.risk.casos_p90 ?? 0) / o.horizon };
  const yMax = niceMax(Math.max(...cases, ...canal, per.hi, 5) * 1.12);
  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const x = (i: number) => M.left + (i / (nCols - 1)) * iw;
  const y = (v: number) => M.top + ih - (v / yMax) * ih;
  const xs = weeks.map((_, i) => x(i));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * yMax);

  // etiquetas de meses en el eje X
  const monthTicks: { i: number; label: string }[] = [];
  let lastMonth = "";
  for (let i = 0; i < nCols; i++) {
    const iso = i < weeks.length ? weeks[i] : addWeeks(o.baseWeek, i - bi);
    const d = new Date(iso + "T12:00:00");
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (key !== lastMonth) {
      lastMonth = key;
      if (i > 0 || nCols < 40) monthTicks.push({ i, label: d.toLocaleDateString("es-PE", { month: "short", year: nCols > 60 ? "2-digit" : undefined }) });
    }
  }
  const every = Math.ceil(monthTicks.length / 14);

  const peaks = findPeaks(cases, canal);
  const aboveIdx = cases.map((v, i) => (v > canal[i] && v >= 5 ? i : -1)).filter((i) => i >= 0);
  const f0 = x(bi);
  const f1 = x(bi + o.horizon);

  const rainMax = niceMax(Math.max(...rain, 10));
  const bw = Math.max(2, iw / nCols - 1.5);

  el.innerHTML = `
  <div class="chart-wrap">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Casos semanales de dengue frente al umbral de brote">
      ${ticks.map((t) => `<line x1="${M.left}" x2="${W - M.right}" y1="${y(t)}" y2="${y(t)}" stroke="var(--border)"/>
        <text x="${M.left - 8}" y="${y(t) + 4}" font-size="11" text-anchor="end" fill="var(--text-3)">${fmt(t)}</text>`).join("")}
      <text x="${M.left}" y="${M.top - 14}" font-size="11" fill="var(--text-3)">casos</text>
      ${monthTicks.filter((_, k) => k % every === 0).map((t) => `<line x1="${x(t.i)}" x2="${x(t.i)}" y1="${M.top + ih}" y2="${M.top + ih + 4}" stroke="var(--text-3)"/>
        <text x="${x(t.i)}" y="${H - 8}" font-size="11" text-anchor="middle" fill="var(--text-3)">${t.label}</text>`).join("")}

      <!-- pronóstico -->
      <rect x="${f0}" y="${M.top}" width="${f1 - f0}" height="${ih}" fill="var(--surface-2)" opacity="0.6"/>
      <rect x="${f0}" y="${y(per.hi)}" width="${f1 - f0}" height="${Math.max(1, y(per.lo) - y(per.hi))}" fill="var(--series-band)" rx="3"/>
      <line x1="${f0}" x2="${f1}" y1="${y(per.mid)}" y2="${y(per.mid)}" stroke="var(--series-1)" stroke-width="2.5" stroke-dasharray="6 4"/>
      <text x="${f1 - 4}" y="${y(per.hi) - 5}" font-size="11" text-anchor="end" fill="var(--text-2)">P90 ${fmt(per.hi)}/sem</text>
      <text x="${f1 - 4}" y="${y(per.lo) + 13}" font-size="11" text-anchor="end" fill="var(--text-2)">P10 ${fmt(per.lo)}/sem</text>
      <line x1="${f0}" x2="${f0}" y1="${M.top - 6}" y2="${M.top + ih}" stroke="var(--text-2)" stroke-width="1.2" stroke-dasharray="3 3"/>
      <text x="${f0}" y="${M.top - 10}" font-size="11" text-anchor="middle" fill="var(--text-2)" font-weight="600">${o.showActual ? "semana de la predicción" : "hoy"}</text>

      <!-- umbral y casos -->
      <path d="${linePath(xs, canal.map(y))}" fill="none" stroke="var(--threshold)" stroke-width="1.6" stroke-dasharray="4 4"/>
      <path d="${linePath(xs, cases.map(y))}" fill="none" stroke="var(--series-1)" stroke-width="2.2" stroke-linejoin="round"/>
      ${aboveIdx.map((i) => `<circle cx="${xs[i]}" cy="${y(cases[i])}" r="3" fill="var(--critical)" stroke="var(--surface)" stroke-width="1.5"/>`).join("")}

      <!-- picos -->
      ${peaks.map((i, k) => {
        const px = xs[i], py = y(cases[i]);
        const left = px > W - 170;
        const tx = left ? px - 10 : px + 10;
        return `<line x1="${px}" x2="${px}" y1="${py - 6}" y2="${py - 26}" stroke="var(--text-2)"/>
          <circle cx="${px}" cy="${py}" r="5" fill="none" stroke="var(--critical)" stroke-width="2"/>
          <text x="${tx}" y="${py - 30}" font-size="12" font-weight="700" text-anchor="${left ? "end" : "start"}" fill="var(--text)">Pico ${k + 1}: ${fmt(cases[i])} casos</text>
          <text x="${tx}" y="${py - 17}" font-size="11" text-anchor="${left ? "end" : "start"}" fill="var(--text-2)">${weekLabel(weeks[i])} · ${fmt(cases[i] / Math.max(canal[i], 1))}× el umbral</text>`;
      }).join("")}

      <line class="xhair" x1="0" x2="0" y1="${M.top}" y2="${M.top + ih}" stroke="var(--text-3)" visibility="hidden"/>
      <circle class="xdot" r="4.5" fill="var(--series-1)" stroke="var(--surface)" stroke-width="2" visibility="hidden"/>
      <rect class="hit" x="${M.left}" y="${M.top}" width="${iw}" height="${ih}" fill="transparent"/>
    </svg>
    <div class="chart-tooltip" hidden></div>
  </div>
  <div class="legend">
    <span><i style="background:var(--series-1)"></i>Casos semanales</span>
    <span><i class="dash"></i>Umbral de brote (canal endémico)</span>
    <span><i style="background:var(--critical);width:10px;height:10px;border-radius:50%"></i>Semana en brote</span>
    <span><i class="box" style="background:var(--series-band)"></i>Rango pronosticado P10–P90</span>
    <span><i style="background:var(--series-1);height:2px;border-top:2px dashed var(--series-1);background:none"></i>Escenario probable (P50)</span>
  </div>
  <p class="eyebrow" style="margin:16px 0 2px">Lluvia semanal (mm) · la de 2 a 6 semanas atrás forma los criaderos</p>
  <svg viewBox="0 0 ${W} ${RAIN_H}" role="img" aria-label="Lluvia semanal">
    <line x1="${M.left}" x2="${W - M.right}" y1="${RAIN_H - 6}" y2="${RAIN_H - 6}" stroke="var(--border)"/>
    <text x="${M.left - 8}" y="16" font-size="11" text-anchor="end" fill="var(--text-3)">${fmt(rainMax)} mm</text>
    <rect x="${f0}" y="4" width="${f1 - f0}" height="${RAIN_H - 10}" fill="var(--surface-2)" opacity="0.6"/>
    ${rain.map((v, i) => {
      const bh = (v / rainMax) * (RAIN_H - 24);
      return `<rect x="${(xs[i] - bw / 2).toFixed(1)}" y="${(RAIN_H - 6 - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0, bh).toFixed(1)}" rx="1.5" fill="var(--rain)"/>`;
    }).join("")}
  </svg>`;

  attachCrosshair(el, (i) => {
    const status = cases[i] > canal[i] && cases[i] >= 5 ? `<span style="color:var(--critical-ink);font-weight:700">En brote</span>` : `Bajo el umbral`;
    return `<strong>Semana del ${weekLabel(weeks[i])}</strong><br>${fmt(cases[i])} casos · umbral ${fmt(canal[i])}<br>Lluvia ${fmt(rain[i])} mm · ${status}`;
  }, xs, cases.map(y), W, M.left, iw, nCols);

  // Resumen para la IA y el informe
  const obsCases = cases.slice(0, bi + 1);
  const last4 = obsCases.slice(-4).reduce((a, b) => a + b, 0);
  const prev4 = obsCases.slice(-8, -4).reduce((a, b) => a + b, 0);
  const tendencia = last4 > prev4 * 1.25 ? "subiendo" : last4 < prev4 * 0.75 ? "bajando" : "estable";
  const summary: HistorySummary = {
    ventana: { desde: weekLabel(weeks[0]), hasta: weekLabel(weeks[bi]), semanas: bi + 1 },
    picos: peaks.map((i) => ({ semana: weekLabel(weeks[i]), casos: cases[i], veces_umbral: Math.round(cases[i] / Math.max(canal[i], 1)) })),
    semanas_en_brote: aboveIdx.filter((i) => i <= bi).length,
    ultimas_8_semanas: obsCases.slice(-8).map((c, k) => { const i = bi - Math.min(7, bi) + k; return { semana: weekLabel(weeks[i]), casos: c, umbral: Math.round(canal[i]), lluvia_mm: Math.round(rain[i]) }; }),
    pronostico_4_semanas: { p10: o.risk.casos_p10 ?? 0, p50: o.risk.casos_p50 ?? 0, p90: o.risk.casos_p90 ?? 0, por_semana_p50: Math.round(per.mid) },
    tendencia,
  };
  if (o.showActual && cases.length > bi + 1) {
    const real = cases.slice(bi + 1, bi + 1 + o.horizon).reduce((a, b) => a + b, 0);
    summary.lo_que_paso = { casos_reales_4_semanas: real, dentro_del_rango: real >= (o.risk.casos_p10 ?? 0) && real <= (o.risk.casos_p90 ?? 0) };
  }
  return summary;
}

export function attachCrosshair(el: HTMLElement, html: (i: number) => string, xs: number[], ys: number[], width: number, left: number, iw: number, nCols: number) {
  const svg = el.querySelector("svg")!;
  const tip = el.querySelector<HTMLDivElement>(".chart-tooltip")!;
  const xhair = svg.querySelector<SVGLineElement>(".xhair")!;
  const dot = svg.querySelector<SVGCircleElement>(".xdot")!;
  const hit = svg.querySelector<SVGRectElement>(".hit")!;
  const move = (clientX: number) => {
    const r = svg.getBoundingClientRect();
    const px = ((clientX - r.left) / r.width) * width;
    const i = Math.max(0, Math.min(xs.length - 1, Math.round(((px - left) / iw) * (nCols - 1))));
    xhair.setAttribute("x1", String(xs[i]));
    xhair.setAttribute("x2", String(xs[i]));
    xhair.setAttribute("visibility", "visible");
    dot.setAttribute("cx", String(xs[i]));
    dot.setAttribute("cy", String(ys[i]));
    dot.setAttribute("visibility", "visible");
    tip.hidden = false;
    tip.innerHTML = html(i);
    const lx = (xs[i] / width) * r.width;
    tip.style.left = `${lx > r.width - 220 ? lx - 230 : lx + 14}px`;
    tip.style.top = `10px`;
  };
  hit.addEventListener("mousemove", (ev) => move(ev.clientX));
  hit.addEventListener("touchmove", (ev) => move(ev.touches[0].clientX), { passive: true });
  const hide = () => { tip.hidden = true; xhair.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); };
  hit.addEventListener("mouseleave", hide);
  hit.addEventListener("touchend", hide);
}

export function addWeeks(iso: string, n: number) {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + 7 * n);
  return d.toISOString().slice(0, 10);
}
