// Optimizador de brigadas de control del dengue. Misma lógica que api/optimizer.py
// (un script de paridad compara ambas implementaciones con los mismos datos).
//
// Beneficio lineal por brigada dentro de cada distrito ⇒ repartir primero donde más casos se
// evitan por brigada es el óptimo exacto (la API lo prueba contra programación dinámica).

export interface OptDistrict {
  district_id: string;
  distrito: string;
  poblacion: number;
  prob: number;
  casos_p10: number;
  casos_p50: number;
  casos_p90: number;
}

export interface OptParams {
  brigadas: number;
  habPorBrigada: number;
  efectividad: number;
  criterio: "probable" | "prudente";
  costoBrigada?: number;
  costoCaso?: number;
}

export interface OptRow extends OptDistrict {
  brigadas: number;
  necesarias: number;
  cobertura: number;
  evitados_p10: number;
  evitados_p50: number;
  evitados_p90: number;
}

export interface OptTotal {
  brigadas: number;
  evitados_p10: number;
  evitados_p50: number;
  evitados_p90: number;
  distritos_cubiertos: number;
}

export interface OptResult {
  optimo: { total: OptTotal; distritos: OptRow[]; pct_casos_evitados: number };
  estrategias: { optimo: OptTotal; por_probabilidad: OptTotal; parejo: OptTotal };
  casos_esperados_total: { p10: number; p50: number; p90: number };
  economia?: { gasto: number; ahorro: number; neto: number; ahorro_por_sol: number | null };
}

const needed = (pop: number, hab: number) => Math.max(1, Math.ceil(pop / hab));
const byId = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

function row(d: OptDistrict, assigned: number, need: number, efect: number): OptRow {
  const cover = need ? Math.min(1, assigned / need) : 0;
  return {
    ...d, brigadas: assigned, necesarias: need, cobertura: Math.round(cover * 1e4) / 1e4,
    evitados_p10: efect * cover * d.casos_p10, evitados_p50: efect * cover * d.casos_p50, evitados_p90: efect * cover * d.casos_p90,
  };
}

function total(rows: OptRow[]): OptTotal {
  return {
    brigadas: rows.reduce((a, r) => a + r.brigadas, 0),
    evitados_p10: rows.reduce((a, r) => a + r.evitados_p10, 0),
    evitados_p50: rows.reduce((a, r) => a + r.evitados_p50, 0),
    evitados_p90: rows.reduce((a, r) => a + r.evitados_p90, 0),
    distritos_cubiertos: rows.filter((r) => r.brigadas > 0).length,
  };
}

export function optimize(districts: OptDistrict[], p: OptParams): OptResult {
  if (p.brigadas < 0 || p.habPorBrigada <= 0 || p.efectividad < 0 || p.efectividad > 1) throw new Error("Parámetros fuera de rango");
  const key = p.criterio === "probable" ? "casos_p50" : "casos_p90";
  const q = key.slice(-3) as "p10" | "p50" | "p90";
  const need: Record<string, number> = {};
  for (const d of districts) need[d.district_id] = needed(d.poblacion, p.habPorBrigada);

  // 1) Óptimo
  let left = p.brigadas;
  const alloc: Record<string, number> = {};
  for (const d of [...districts].sort((a, b) => (b[key] / need[b.district_id] - a[key] / need[a.district_id]) || byId(a.district_id, b.district_id))) {
    const give = Math.min(need[d.district_id], left);
    alloc[d.district_id] = give;
    left -= give;
  }
  const optimo = districts.map((d) => row(d, alloc[d.district_id], need[d.district_id], p.efectividad));

  // 2) Por probabilidad (ranking del panel), distritos completos
  left = p.brigadas;
  const allocP: Record<string, number> = {};
  for (const d of [...districts].sort((a, b) => (b.prob - a.prob) || byId(a.district_id, b.district_id))) {
    const give = Math.min(need[d.district_id], left);
    allocP[d.district_id] = give;
    left -= give;
  }
  const porProb = districts.map((d) => row(d, allocP[d.district_id], need[d.district_id], p.efectividad));

  // 3) Parejo por población (mayor resto), sin pasar de lo necesario
  const totalPop = districts.reduce((a, d) => a + d.poblacion, 0) || 1;
  const raw: Record<string, number> = {};
  for (const d of districts) raw[d.district_id] = (p.brigadas * d.poblacion) / totalPop;
  const allocE: Record<string, number> = {};
  for (const d of districts) allocE[d.district_id] = Math.min(Math.floor(raw[d.district_id]), need[d.district_id]);
  let spare = p.brigadas - Object.values(allocE).reduce((a, b) => a + b, 0);
  const ids = districts.map((d) => d.district_id);
  ids.sort((a, b) => -(raw[a] - Math.floor(raw[a])) - -(raw[b] - Math.floor(raw[b])));
  for (const id of ids) {
    if (spare <= 0) break;
    if (allocE[id] < need[id]) { allocE[id] += 1; spare -= 1; }
  }
  const parejo = districts.map((d) => row(d, allocE[d.district_id], need[d.district_id], p.efectividad));

  const esperados = {
    p10: districts.reduce((a, d) => a + d.casos_p10, 0),
    p50: districts.reduce((a, d) => a + d.casos_p50, 0),
    p90: districts.reduce((a, d) => a + d.casos_p90, 0),
  };
  const t = total(optimo);
  const out: OptResult = {
    optimo: {
      total: t,
      distritos: optimo.filter((r) => r.brigadas > 0).sort((a, b) => b[`evitados_${q}`] - a[`evitados_${q}`]),
      pct_casos_evitados: Math.round((1000 * t[`evitados_${q}`]) / Math.max(1, esperados[q])) / 10,
    },
    estrategias: { optimo: t, por_probabilidad: total(porProb), parejo: total(parejo) },
    casos_esperados_total: esperados,
  };
  if (p.costoBrigada !== undefined && p.costoCaso !== undefined) {
    const gasto = t.brigadas * p.costoBrigada;
    const ahorro = t[`evitados_${q}`] * p.costoCaso;
    out.economia = { gasto: Math.round(gasto), ahorro: Math.round(ahorro), neto: Math.round(ahorro - gasto), ahorro_por_sol: gasto ? Math.round((100 * ahorro) / gasto) / 100 : null };
  }
  return out;
}
