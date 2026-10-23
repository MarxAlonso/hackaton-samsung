// Mapa de calor distrito × semana: incidencia de dengue por 100 mil habitantes.
// Rampa secuencial de un solo tono (azul), de claro a oscuro. Las 4 columnas finales son el pronóstico.
import type { District, DistrictPrediction, SeriesData } from "./data";
import { fmt, weekLabel } from "./data";

const CELL = 13;
const GAP = 1.5;
const LEFT = 150;
const TOP = 36;
const RAMP = ["--seq-0", "--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6", "--seq-7"];

export interface HeatmapOpts {
  baseWeek: string;
  weeksBack: number;
  horizon: number;
  rows: { district: District; pred: DistrictPrediction }[]; // orden = prioridad
  selected: string;
  onSelect: (id: string) => void;
  metric: "inc" | "dengue";
}

function binEdges(values: number[]) {
  // Cortes por cuantiles sobre valores > 0 para que la rampa aproveche todos los tonos
  const pos = values.filter((v) => v > 0).sort((a, b) => a - b);
  if (!pos.length) return [1, 2, 3, 4, 5, 6, 7];
  const q = (p: number) => pos[Math.min(pos.length - 1, Math.floor(p * pos.length))];
  return [q(0.15), q(0.3), q(0.45), q(0.6), q(0.75), q(0.88), q(0.96)];
}

export interface HeatmapSummary {
  medida: string;
  semanas_observadas: number;
  distritos_mas_afectados_ultimas_4_semanas: { distrito: string; valor: number }[];
  distritos_con_mayor_pronostico: { distrito: string; valor_por_semana: number }[];
  distritos_sin_casos_recientes: number;
}

export function renderHeatmap(el: HTMLElement, series: SeriesData, o: HeatmapOpts): HeatmapSummary {
  const all = series.semanas;
  const baseIdx = all.indexOf(o.baseWeek);
  const start = Math.max(0, baseIdx - o.weeksBack + 1);
  const weeks = all.slice(start, baseIdx + 1);
  const nObs = weeks.length;
  const nCols = nObs + o.horizon;
  const unit = o.metric === "inc" ? "por 100 mil hab." : "casos";

  // matriz de valores observados + pronóstico (P50 repartido por semana, en la misma unidad)
  const matrix = o.rows.map(({ district, pred }) => {
    const s = series.distritos[district.district_id];
    const obs = s[o.metric].slice(start, baseIdx + 1);
    const p50 = (pred.riesgos.dengue.casos_p50 ?? 0) / o.horizon;
    const fc = o.metric === "inc" ? (p50 / district.population) * 1e5 : p50;
    return [...obs, ...Array(o.horizon).fill(fc)];
  });
  const edges = binEdges(matrix.flat());
  const color = (v: number) => {
    if (v <= 0) return `var(${RAMP[0]})`;
    let k = 1;
    while (k < RAMP.length - 1 && v > edges[k - 1]) k++;
    return `var(${RAMP[k]})`;
  };

  const width = LEFT + nCols * (CELL + GAP) + 24;
  const height = TOP + o.rows.length * (CELL + GAP) + 8;
  const cx = (c: number) => LEFT + c * (CELL + GAP) + (c >= nObs ? 6 : 0);
  const cy = (r: number) => TOP + r * (CELL + GAP);

  // etiquetas de meses
  let lastMonth = "";
  const months: { c: number; label: string }[] = [];
  weeks.forEach((iso, c) => {
    const d = new Date(iso + "T12:00:00");
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (key !== lastMonth) { lastMonth = key; months.push({ c, label: d.toLocaleDateString("es-PE", { month: "short", year: nObs > 60 ? "2-digit" : undefined }) }); }
  });
  const every = Math.ceil(months.length / 16);

  el.innerHTML = `
  <div class="chart-wrap heat-scroll">
    <svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" style="width:${width}px;max-width:none" role="img" aria-label="Mapa de calor de incidencia de dengue por distrito y semana">
      ${months.filter((_, k) => k % every === 0).map((m) => `<text x="${cx(m.c)}" y="14" font-size="11" fill="var(--text-3)">${m.label}</text>
        <line x1="${cx(m.c)}" x2="${cx(m.c)}" y1="18" y2="${TOP - 4}" stroke="var(--border)"/>`).join("")}
      <text x="${cx(nObs) + (o.horizon * (CELL + GAP)) / 2}" y="14" font-size="11" font-weight="700" text-anchor="middle" fill="var(--brand)">pronóstico</text>
      <line x1="${cx(nObs) - 3.5}" x2="${cx(nObs) - 3.5}" y1="${TOP - 2}" y2="${height - 6}" stroke="var(--text-2)" stroke-dasharray="3 3"/>
      ${o.rows.map(({ district }, r) => `<text class="hm-label" data-id="${district.district_id}" x="${LEFT - 8}" y="${cy(r) + CELL - 2}" font-size="11.5" text-anchor="end" fill="${district.district_id === o.selected ? "var(--brand)" : "var(--text-2)"}" font-weight="${district.district_id === o.selected ? 700 : 400}" style="cursor:pointer">${district.district}</text>`).join("")}
      ${matrix.map((row, r) => row.map((v, c) => `<rect class="hm-cell" data-r="${r}" data-c="${c}" x="${cx(c)}" y="${cy(r)}" width="${CELL}" height="${CELL}" rx="2.5" fill="${color(v)}" ${c >= nObs ? `stroke="var(--brand)" stroke-width="0.8" stroke-dasharray="2 1.5"` : ""} style="cursor:pointer"/>`).join("")).join("")}
    </svg>
    <div class="chart-tooltip" hidden></div>
  </div>
  <div class="legend" style="align-items:center">
    <span>Incidencia (${unit}):</span>
    <span style="gap:2px">${RAMP.map((v) => `<i class="box" style="background:var(${v});width:18px"></i>`).join("")}</span>
    <span class="muted">0 → ${fmt(edges[edges.length - 1])}+</span>
    <span><i class="box" style="background:var(--surface-2);border:1px dashed var(--brand);width:16px"></i>Pronóstico (P50 por semana)</span>
    <span class="muted">Filas ordenadas por prioridad de hoy · clic en un distrito para ver su detalle</span>
  </div>`;

  const tip = el.querySelector<HTMLDivElement>(".chart-tooltip")!;
  const wrap = el.querySelector<HTMLElement>(".heat-scroll")!;
  el.querySelectorAll<SVGRectElement>(".hm-cell").forEach((rect) => {
    rect.addEventListener("mouseenter", () => {
      const r = Number(rect.dataset.r), c = Number(rect.dataset.c);
      const { district } = o.rows[r];
      const s = series.distritos[district.district_id];
      const isFc = c >= nObs;
      const v = matrix[r][c];
      const label = isFc ? `Pronóstico, semana +${c - nObs + 1}` : `Semana del ${weekLabel(weeks[c])}`;
      const extra = isFc ? "" : `<br>${fmt(s.dengue[start + c])} casos · lluvia ${fmt(s.lluvia[start + c])} mm`;
      tip.innerHTML = `<strong>${district.district}</strong> · ${label}<br>${o.metric === "inc" ? `${v.toFixed(1)} por 100 mil` : `${fmt(v)} casos`}${extra}`;
      tip.hidden = false;
      const bx = rect.getBoundingClientRect(), wx = wrap.getBoundingClientRect();
      const lx = bx.left - wx.left + wrap.scrollLeft;
      tip.style.left = `${lx > wx.width - 230 ? lx - 240 : lx + 18}px`;
      tip.style.top = `${bx.top - wx.top + 18}px`;
      rect.setAttribute("stroke", "var(--text)");
      rect.setAttribute("stroke-width", "1.5");
      rect.removeAttribute("stroke-dasharray");
    });
    rect.addEventListener("mouseleave", () => {
      tip.hidden = true;
      const c = Number(rect.dataset.c);
      if (c >= nObs) { rect.setAttribute("stroke", "var(--brand)"); rect.setAttribute("stroke-width", "0.8"); rect.setAttribute("stroke-dasharray", "2 1.5"); }
      else rect.removeAttribute("stroke");
    });
    rect.addEventListener("click", () => o.onSelect(o.rows[Number(rect.dataset.r)].district.district_id));
  });
  el.querySelectorAll<SVGTextElement>(".hm-label").forEach((t) => t.addEventListener("click", () => o.onSelect(t.dataset.id!)));
  // Desplaza al final (pronóstico) la primera vez
  wrap.scrollLeft = wrap.scrollWidth;

  const recent = o.rows.map(({ district }, r) => ({ distrito: district.district, valor: Math.round(matrix[r].slice(nObs - 4, nObs).reduce((a, b) => a + b, 0) * 10) / 10 }));
  const fc = o.rows.map(({ district }, r) => ({ distrito: district.district, valor_por_semana: Math.round(matrix[r][nObs] * 10) / 10 }));
  return {
    medida: unit,
    semanas_observadas: nObs,
    distritos_mas_afectados_ultimas_4_semanas: [...recent].sort((a, b) => b.valor - a.valor).slice(0, 6),
    distritos_con_mayor_pronostico: [...fc].sort((a, b) => b.valor_por_semana - a.valor_por_semana).slice(0, 6),
    distritos_sin_casos_recientes: recent.filter((r) => r.valor === 0).length,
  };
}
