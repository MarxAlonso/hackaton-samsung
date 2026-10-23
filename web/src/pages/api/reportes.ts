// Reportes ciudadanos anónimos: "veo criaderos" o "hay personas con fiebre" en mi distrito.
// Diseño pensado para la privacidad y el abuso:
//  - Solo se guarda un CONTADOR por distrito, tipo y semana. Sin texto libre, sin dirección IP, sin identificador.
//  - Hay un tope diario por distrito: si alguien intenta inflar los números, se detiene.
//  - Es una señal SIN VERIFICAR: se muestra a la autoridad con ese rótulo y nunca entra al modelo.
import type { APIRoute } from "astro";

export const prerender = false;

const DISTRICT = /^(tum|piu|lam)-[a-z0-9]{3,20}$/;
const TIPOS = ["criaderos", "fiebre"] as const;
type Tipo = (typeof TIPOS)[number];
const DAILY_CAP = 40;                     // reportes por distrito y día
const TTL = 60 * 60 * 24 * 60;            // los contadores vencen a los 60 días
const MAX_BODY = 512;

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "cache-control": "no-store" } });
const weekIndex = (t = Date.now()) => Math.floor(t / (7 * 24 * 3600 * 1000));
const dayKey = () => new Date().toISOString().slice(0, 10);

async function kv() {
  const { env } = await import("cloudflare:workers");
  const store = (env as { ALERTAS?: KVNamespace }).ALERTAS;
  if (!store) throw new Error("Sin almacenamiento");
  return store;
}

export const POST: APIRoute = async ({ request }) => {
  let body: any;
  try {
    const text = await request.text();
    if (text.length > MAX_BODY) throw new Error("grande");
    body = JSON.parse(text);
  } catch { return json({ error: "Solicitud inválida" }, 400); }
  const { distrito, tipo } = body ?? {};
  if (!DISTRICT.test(String(distrito)) || !TIPOS.includes(tipo)) return json({ error: "Solicitud inválida" }, 400);
  try {
    const store = await kv();
    const capKey = `repday:${distrito}:${dayKey()}`;
    const today = Number((await store.get(capKey)) ?? 0);
    if (today >= DAILY_CAP) return json({ error: "Hoy ya se recibieron muchos reportes de este distrito. Vuelve mañana." }, 429);
    await store.put(capKey, String(today + 1), { expirationTtl: 60 * 60 * 36 });
    const key = `rep:${distrito}:${tipo as Tipo}:${weekIndex()}`;
    const n = Number((await store.get(key)) ?? 0);
    await store.put(key, String(n + 1), { expirationTtl: TTL });
    return json({ ok: true });
  } catch {
    return json({ error: "No se pudo guardar" }, 500);
  }
};

/** Conteos de las últimas 2 semanas (la actual y la anterior). Con ?d= un distrito; sin él, todos. */
export const GET: APIRoute = async ({ url }) => {
  const d = url.searchParams.get("d");
  if (d && !DISTRICT.test(d)) return json({ error: "Distrito inválido" }, 400);
  try {
    const store = await kv();
    const now = weekIndex();
    const out: Record<string, { criaderos: number; fiebre: number }> = {};
    let cursor: string | undefined;
    do {
      const page = await store.list({ prefix: d ? `rep:${d}:` : "rep:", cursor, limit: 1000 });
      for (const k of page.keys) {
        const [, dist, tipo, week] = k.name.split(":");
        if (now - Number(week) > 1 || !TIPOS.includes(tipo as Tipo)) continue;
        const n = Number((await store.get(k.name)) ?? 0);
        (out[dist] ??= { criaderos: 0, fiebre: 0 })[tipo as Tipo] += n;
      }
      cursor = page.list_complete ? undefined : page.cursor;
    } while (cursor);
    return json({ ventana: "últimas 2 semanas", sin_verificar: true, distritos: out });
  } catch {
    return json({ distritos: {}, sin_verificar: true });
  }
};
