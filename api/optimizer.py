"""Optimizador de brigadas de control del dengue.

Pregunta de negocio: "Tengo B brigadas para las próximas 4 semanas. ¿En qué distritos las pongo
para evitar la mayor cantidad de casos?"

Modelo del problema (supuestos editables, declarados a la autoridad):
  - Cubrir un distrito completo requiere ceil(población / habitantes_por_brigada) brigadas.
  - Con cobertura c (0–1) se evita una fracción  efectividad × c  de los casos esperados.
  - Los casos esperados salen del modelo: P50 (criterio "probable") o P90 ("prudente").

Como el beneficio es lineal en el número de brigadas de cada distrito, el óptimo exacto se obtiene
repartiendo primero donde más casos se evitan por brigada (se prueba contra programación dinámica
en los tests). Se compara con dos reglas que una oficina usaría sin optimizar:
  - "por_probabilidad": cubrir completos los distritos del ranking, de mayor a menor probabilidad.
  - "parejo": repartir las brigadas en proporción a la población.

La misma lógica corre en el navegador (web/src/lib/optimizer.ts); un test de paridad vigila que coincidan.
"""
import math

CRITERIOS = {"probable": "casos_p50", "prudente": "casos_p90"}


def _needed(pop, hab_por_brigada):
    return max(1, math.ceil(pop / hab_por_brigada))


def _row(d, assigned, needed, efectividad):
    cover = min(1.0, assigned / needed) if needed else 0.0
    out = {
        "district_id": d["district_id"], "distrito": d.get("distrito", d["district_id"]),
        "poblacion": d["poblacion"], "prob": d["prob"],
        "brigadas": assigned, "necesarias": needed, "cobertura": round(cover, 4),
    }
    for k in ("casos_p10", "casos_p50", "casos_p90"):
        out[k] = d[k]
        out["evitados_" + k[-3:]] = efectividad * cover * d[k]
    return out


def _total(rows):
    t = {"brigadas": sum(r["brigadas"] for r in rows)}
    for q in ("p10", "p50", "p90"):
        t["evitados_" + q] = sum(r["evitados_" + q] for r in rows)
    t["distritos_cubiertos"] = sum(1 for r in rows if r["brigadas"] > 0)
    return t


def optimize(districts, brigadas, hab_por_brigada=15000, efectividad=0.30, criterio="probable",
             costo_brigada=None, costo_caso=None):
    """districts: lista de dicts con district_id, distrito, poblacion, prob, casos_p10/p50/p90."""
    if brigadas < 0 or hab_por_brigada <= 0 or not 0 <= efectividad <= 1:
        raise ValueError("Parámetros fuera de rango")
    key = CRITERIOS[criterio]
    need = {d["district_id"]: _needed(d["poblacion"], hab_por_brigada) for d in districts}

    # 1) Óptimo: mayor beneficio por brigada primero (el beneficio es lineal dentro de cada distrito)
    order = sorted(districts, key=lambda d: (-d[key] / need[d["district_id"]], d["district_id"]))
    left, alloc = brigadas, {}
    for d in order:
        give = min(need[d["district_id"]], left)
        alloc[d["district_id"]] = give
        left -= give
    optimo = [_row(d, alloc[d["district_id"]], need[d["district_id"]], efectividad) for d in districts]

    # 2) Regla "por probabilidad": completos, en el orden del ranking del panel
    left, alloc_p = brigadas, {}
    for d in sorted(districts, key=lambda d: (-d["prob"], d["district_id"])):
        give = min(need[d["district_id"]], left)
        alloc_p[d["district_id"]] = give
        left -= give
    por_prob = [_row(d, alloc_p[d["district_id"]], need[d["district_id"]], efectividad) for d in districts]

    # 3) Reparto parejo por población (máximo remanente), sin pasar de lo necesario
    total_pop = sum(d["poblacion"] for d in districts) or 1
    raw = {d["district_id"]: brigadas * d["poblacion"] / total_pop for d in districts}
    alloc_e = {k: min(math.floor(v), need[k]) for k, v in raw.items()}
    spare = brigadas - sum(alloc_e.values())
    for k in sorted(raw, key=lambda k: -(raw[k] - math.floor(raw[k]))):
        if spare <= 0:
            break
        if alloc_e[k] < need[k]:
            alloc_e[k] += 1
            spare -= 1
    parejo = [_row(d, alloc_e[d["district_id"]], need[d["district_id"]], efectividad) for d in districts]

    result = {
        "parametros": {"brigadas": brigadas, "hab_por_brigada": hab_por_brigada, "efectividad": efectividad, "criterio": criterio},
        "optimo": {"total": _total(optimo), "distritos": sorted([r for r in optimo if r["brigadas"] > 0], key=lambda r: -r["evitados_" + key[-3:]])},
        "estrategias": {"optimo": _total(optimo), "por_probabilidad": _total(por_prob), "parejo": _total(parejo)},
        "casos_esperados_total": {q: sum(d["casos_" + q] for d in districts) for q in ("p10", "p50", "p90")},
    }
    t = result["optimo"]["total"]
    result["optimo"]["pct_casos_evitados"] = round(100 * t["evitados_" + key[-3:]] / max(1, result["casos_esperados_total"][key[-3:]]), 1)
    if costo_brigada is not None and costo_caso is not None:
        gasto = t["brigadas"] * costo_brigada
        ahorro = t["evitados_" + key[-3:]] * costo_caso
        result["economia"] = {"gasto": round(gasto), "ahorro": round(ahorro), "neto": round(ahorro - gasto),
                              "ahorro_por_sol": round(ahorro / gasto, 2) if gasto else None}
    return result
