// Comparaciones: (1) temporadas superpuestas por semana del año; (2) dos distritos lado a lado.
import type { District, SeriesData } from "./data";
import { fmt, weekLabel } from "./data";
import { W, attachCrosshair, linePath, niceMax } from "./chart";

const H = 320;
const M = { top: 24, right: 90, bottom: 30, left: 52 };
const SEASON_COLORS: Record<string, string> = { "2017": "var(--series-2)", "2023": "var(--series-1)" };
const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];

function epiweek(iso: string) {
  const d = new Date(iso + "T12:00:00");
  const start = new Date(d.getFullYear(), 0, 1);
  return Math.min(52, Math.floor((d.getTime() - start.getTime()) / 6048e5) + 1);
}

/** Superpone los años por semana del año. Destaca 2017, 2023 y el año actual; el resto en gris. */
export function renderSeasons(el: HTMLElement, series: SeriesData, districtId: string, district: District, metric: "inc" | "dengue") {
  const s = series.distritos[districtId];
  const byYear: Record<string, number[]> = {};
  series.semanas.forEach((iso, i) => {
    const yr = iso.slice(0, 4);
    (byYear[yr] ??= Array(52).fill(NaN))[epiweek(iso) - 1] = s[metric][i];
  });
  // Solo años con algún dato oficial: el año en curso puede no tener casos todavía
  const years = Object.keys(byYear).filter((y) => Number(y) >= 2016 && byYear[y].some((v) => !isNaN(v))).sort();
  const current = years[years.length - 1];
  const lastYear = series.semanas[series.semanas.length - 1].slice(0, 4);
  const highlight = new Set(["2017", "2023", current]);
  const colorOf = (y: string) => (y === current ? "var(--series-3)" : SEASON_COLORS[y] ?? "var(--border)");

  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  // La escala sigue a los años destacados; los demás se dibujan recortados para no aplastar la lectura
  const yMax = niceMax(Math.max(5, ...[...highlight].flatMap((yv) => (byYear[yv] ?? []).filter((v) => !isNaN(v)))) * 1.15);
  const x = (w: number) => M.left + (w / 51) * iw;
  const y = (v: number) => M.top + ih - (v / yMax) * ih;
  const xs = Array.from({ length: 52 }, (_, w) => x(w));
  const path = (vals: number[]) => {
    const pts = vals.map((v, w) => (isNaN(v) ? null : `${x(w).toFixed(1)},${y(v).toFixed(1)}`));
    let d = "", pen = false;
    for (const p of pts) { if (!p) { pen = false; continue; } d += (pen ? "L" : "M") + p; pen = true; }
    return d;
  };
  const ticks = [0, 0.5, 1].map((t) => t * yMax);
  const unit = metric === "inc" ? "por 100 mil" : "casos";

  // totales por temporada para la tabla
  const totals = [...highlight].filter((y) => byYear[y]).map((y) => {
    const vals = byYear[y].filter((v) => !isNaN(v));
    const peak = Math.max(...vals);
    const peakW = byYear[y].indexOf(peak);
    return { y, total: vals.reduce((a, b) => a + b, 0), peak, peakW };
  }).sort((a, b) => Number(a.y) - Number(b.y));

  el.innerHTML = `
  <div class="chart-wrap">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Comparación de temporadas de dengue por semana del año">
      ${ticks.map((t) => `<line x1="${M.left}" x2="${W - M.right}" y1="${y(t)}" y2="${y(t)}" stroke="var(--border)"/>
        <text x="${M.left - 8}" y="${y(t) + 4}" font-size="11" text-anchor="end" fill="var(--text-3)">${metric === "inc" ? t.toFixed(0) : fmt(t)}</text>`).join("")}
      <text x="${M.left}" y="${M.top - 8}" font-size="11" fill="var(--text-3)">${unit}</text>
      <clipPath id="clip-seasons"><rect x="${M.left}" y="${M.top}" width="${iw}" height="${ih}"/></clipPath>
      ${MONTHS.map((m, k) => `<text x="${x(k * 4.33 + 2)}" y="${H - 10}" font-size="11" text-anchor="middle" fill="var(--text-3)">${m}</text>`).join("")}
      ${years.filter((yv) => !highlight.has(yv)).map((yv) => `<path d="${path(byYear[yv])}" fill="none" stroke="var(--surface-3)" stroke-width="1.4" clip-path="url(#clip-seasons)"/>`).join("")}
      ${[...highlight].filter((yv) => byYear[yv]).map((yv) => `<path d="${path(byYear[yv])}" fill="none" stroke="${colorOf(yv)}" stroke-width="2.4" stroke-linejoin="round"/>`).join("")}
      ${totals.map((t) => {
        const px = x(t.peakW), py = y(t.peak);
        const left = px > W - M.right - 120;
        return `<circle cx="${px}" cy="${py}" r="4" fill="${colorOf(t.y)}" stroke="var(--surface)" stroke-width="1.5"/>
          <text x="${left ? px - 8 : px + 8}" y="${py - 6}" font-size="12" font-weight="700" text-anchor="${left ? "end" : "start"}" fill="${colorOf(t.y)}">${t.y}${t.y === current ? (current === lastYear ? " (hoy)" : " (último con datos)") : ""} · pico ${metric === "inc" ? t.peak.toFixed(0) : fmt(t.peak)}</text>`;
      }).join("")}
      <line class="xhair" x1="0" x2="0" y1="${M.top}" y2="${M.top + ih}" stroke="var(--text-3)" visibility="hidden"/>
      <circle class="xdot" r="0" visibility="hidden"/>
      <rect class="hit" x="${M.left}" y="${M.top}" width="${iw}" height="${ih}" fill="transparent"/>
    </svg>
    <div class="chart-tooltip" hidden></div>
  </div>
  <div class="legend">
    ${totals.map((t) => `<span><i style="background:${colorOf(t.y)}"></i>${t.y}${t.y === current ? (current === lastYear ? " (en curso)" : " (último con datos)") : ""}</span>`).join("")}
    <span><i style="background:var(--surface-3)"></i>Otros años</span>
  </div>
  <table class="mini">
    <thead><tr><th>Temporada</th><th>Total ${unit}</th><th>Pico semanal</th><th>Semana del pico</th></tr></thead>
    <tbody>${totals.map((t) => `<tr><td><strong style="color:${colorOf(t.y)}">${t.y}</strong></td><td>${metric === "inc" ? t.total.toFixed(0) : fmt(t.total)}</td><td>${metric === "inc" ? t.peak.toFixed(1) : fmt(t.peak)}</td><td>${MONTHS[Math.min(11, Math.floor(t.peakW / 4.33))]} (sem. ${t.peakW + 1})</td></tr>`).join("")}</tbody>
  </table>`;

  attachCrosshair(el, (w) => `<strong>Semana ${w + 1} del año</strong><br>` + totals.map((t) => {
    const v = byYear[t.y][w];
    return `<span style="color:${colorOf(t.y)};font-weight:700">${t.y}</span>: ${isNaN(v) ? "—" : metric === "inc" ? v.toFixed(1) : fmt(v)}`;
  }).join("<br>"), xs, xs.map(() => M.top), W, M.left, iw, 52);

  return {
    distrito: district.district,
    medida: unit,
    temporadas: totals.map((t) => ({ anio: t.y, en_curso: t.y === current && current === lastYear, total: Math.round(t.total), pico_semanal: Math.round(t.peak * 10) / 10, mes_del_pico: MONTHS[Math.min(11, Math.floor(t.peakW / 4.33))] })),
  };
}

/** Dos distritos en la misma ventana, en incidencia por 100 mil para que sea comparable. */
export function renderDistrictCompare(el: HTMLElement, series: SeriesData, a: District, b: District, baseWeek: string, weeksBack: number) {
  const all = series.semanas;
  const baseIdx = all.indexOf(baseWeek);
  const start = Math.max(0, baseIdx - weeksBack + 1);
  const weeks = all.slice(start, baseIdx + 1);
  const sa = series.distritos[a.district_id], sb = series.distritos[b.district_id];
  const va = sa.inc.slice(start, baseIdx + 1), vb = sb.inc.slice(start, baseIdx + 1);
  const ra = sa.lluvia.slice(start, baseIdx + 1), rb = sb.lluvia.slice(start, baseIdx + 1);

  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  const fin = (a: number[]) => a.filter(Number.isFinite);
  const lastFin = (a: number[]) => { const f = a.filter(Number.isFinite); return f.length ? f[f.length - 1] : 0; };
  const yMax = niceMax(Math.max(5, ...fin(va), ...fin(vb)) * 1.08);
  const x = (i: number) => M.left + (i / (weeks.length - 1)) * iw;
  const y = (v: number) => M.top + ih - (v / yMax) * ih;
  const xs = weeks.map((_, i) => x(i));
  const ticks = [0, 0.5, 1].map((t) => t * yMax);
  let lastMonth = "";
  const months: { i: number; label: string }[] = [];
  weeks.forEach((iso, i) => {
    const d = new Date(iso + "T12:00:00"); const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (key !== lastMonth) { lastMonth = key; months.push({ i, label: d.toLocaleDateString("es-PE", { month: "short", year: weeks.length > 60 ? "2-digit" : undefined }) }); }
  });
  const every = Math.ceil(months.length / 14);
  const sum = (v: number[]) => v.reduce((p, c) => p + c, 0);
  const okSum = (a: number[]) => { const f = a.filter(Number.isFinite); return f.length ? fmt(sum(f)) + (f.length < a.length ? ` <span class="small muted">(${a.length - f.length} sem. sin dato)</span>` : "") : `<span class="muted">sin dato oficial</span>`; };
  const okMax = (a: number[]) => { const f = a.filter(Number.isFinite); return f.length ? fmt(Math.max(...f)) : `<span class="muted">—</span>`; };
  const stats = [[a, va, ra, sa, "var(--series-1)"], [b, vb, rb, sb, "var(--series-2)"]] as const;

  el.innerHTML = `
  <div class="chart-wrap">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Comparación de dos distritos">
      ${ticks.map((t) => `<line x1="${M.left}" x2="${W - M.right}" y1="${y(t)}" y2="${y(t)}" stroke="var(--border)"/>
        <text x="${M.left - 8}" y="${y(t) + 4}" font-size="11" text-anchor="end" fill="var(--text-3)">${t.toFixed(0)}</text>`).join("")}
      <text x="${M.left}" y="${M.top - 8}" font-size="11" fill="var(--text-3)">por 100 mil</text>
      ${months.filter((_, k) => k % every === 0).map((m) => `<text x="${x(m.i)}" y="${H - 10}" font-size="11" text-anchor="middle" fill="var(--text-3)">${m.label}</text>`).join("")}
      <path d="${linePath(xs, va.map(y))}" fill="none" stroke="var(--series-1)" stroke-width="2.4" stroke-linejoin="round"/>
      <path d="${linePath(xs, vb.map(y))}" fill="none" stroke="var(--series-2)" stroke-width="2.4" stroke-linejoin="round"/>
      <text x="${xs[xs.length - 1] + 6}" y="${y(lastFin(va)) + 4}" font-size="12" font-weight="700" fill="var(--series-1)">${a.district}</text>
      <text x="${xs[xs.length - 1] + 6}" y="${y(lastFin(vb)) + 4 + (Math.abs(y(lastFin(va)) - y(lastFin(vb))) < 14 ? 14 : 0)}" font-size="12" font-weight="700" fill="var(--series-2)">${b.district}</text>
      <line class="xhair" x1="0" x2="0" y1="${M.top}" y2="${M.top + ih}" stroke="var(--text-3)" visibility="hidden"/>
      <circle class="xdot" r="0" visibility="hidden"/>
      <rect class="hit" x="${M.left}" y="${M.top}" width="${iw}" height="${ih}" fill="transparent"/>
    </svg>
    <div class="chart-tooltip" hidden></div>
  </div>
  <div class="legend"><span><i style="background:var(--series-1)"></i>${a.district}</span><span><i style="background:var(--series-2)"></i>${b.district}</span></div>
  <table class="mini">
    <thead><tr><th>Distrito</th><th>Población</th><th>Casos en la ventana</th><th>Pico semanal</th><th>Lluvia acumulada</th><th>Agua por red</th></tr></thead>
    <tbody>${stats.map(([d, v, r, s, col]) => `<tr><td><strong style="color:${col}">${d.district}</strong><br><span class="small muted">${d.department}</span></td><td>${fmt(d.population)}</td><td>${okSum(s.dengue.slice(start, baseIdx + 1))}</td><td>${okMax(s.dengue.slice(start, baseIdx + 1))}</td><td>${fmt(sum(r))} mm</td><td>${Math.round(d.water_access * 100)}%</td></tr>`).join("")}</tbody>
  </table>`;

  attachCrosshair(el, (i) => `<strong>Semana del ${weekLabel(weeks[i])}</strong><br><span style="color:var(--series-1);font-weight:700">${a.district}</span>: ${va[i].toFixed(1)} por 100 mil · ${fmt(ra[i])} mm<br><span style="color:var(--series-2);font-weight:700">${b.district}</span>: ${vb[i].toFixed(1)} por 100 mil · ${fmt(rb[i])} mm`,
    xs, xs.map(() => M.top), W, M.left, iw, weeks.length);

  return {
    ventana: { desde: weekLabel(weeks[0]), hasta: weekLabel(weeks[weeks.length - 1]) },
    distritos: stats.map(([d, v, r, s]) => ({
      distrito: d.district, departamento: d.department, poblacion: d.population, agua_por_red_pct: Math.round(d.water_access * 100),
      casos: fin(s.dengue.slice(start, baseIdx + 1)).length ? sum(fin(s.dengue.slice(start, baseIdx + 1))) : null,
      pico_semanal_casos: fin(s.dengue.slice(start, baseIdx + 1)).length ? Math.max(...fin(s.dengue.slice(start, baseIdx + 1))) : null,
      incidencia_acumulada_100k: fin(v).length ? Math.round(sum(fin(v))) : null, lluvia_acumulada_mm: Math.round(sum(r)),
      semanas_sin_dato_oficial: v.length - fin(v).length,
    })),
  };
}
