// Suscripciones a alertas push. Solo se guarda la dirección técnica del navegador y el distrito:
// no hay nombre, teléfono ni ubicación. El envío lo hace ml/src/notify.py desde GitHub Actions.
import type { APIRoute } from "astro";

export const prerender = false;

// Solo servicios de push conocidos: así nadie puede registrar una dirección arbitraria
const PUSH_HOSTS = [/(^|\.)googleapis\.com$/, /(^|\.)mozilla\.com$/, /(^|\.)windows\.com$/, /(^|\.)push\.apple\.com$/];
const DISTRICT = /^(tum|piu|lam)-[a-z0-9]{3,20}$/;
const MAX_BODY = 4096;
const TTL = 60 * 60 * 24 * 200; // vence a los 200 días si no se vuelve a suscribir

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "cache-control": "no-store" } });

async function keyFor(endpoint: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(endpoint));
  return "sub:" + [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function readBody(request: Request) {
  const text = await request.text();
  if (text.length > MAX_BODY) throw new Error("grande");
  return JSON.parse(text);
}

function validEndpoint(endpoint: unknown): endpoint is string {
  if (typeof endpoint !== "string" || endpoint.length > 600) return false;
  try {
    const u = new URL(endpoint);
    return u.protocol === "https:" && PUSH_HOSTS.some((re) => re.test(u.hostname));
  } catch {
    return false;
  }
}

async function kv() {
  const { env } = await import("cloudflare:workers");
  const store = (env as { ALERTAS?: KVNamespace }).ALERTAS;
  if (!store) throw new Error("Sin almacenamiento de alertas");
  return store;
}

export const POST: APIRoute = async ({ request }) => {
  let body: any;
  try { body = await readBody(request); } catch { return json({ error: "Solicitud inválida" }, 400); }
  const sub = body?.suscripcion;
  const distrito = body?.distrito;
  if (!validEndpoint(sub?.endpoint) || typeof sub?.keys?.p256dh !== "string" || typeof sub?.keys?.auth !== "string"
      || sub.keys.p256dh.length > 200 || sub.keys.auth.length > 100 || !DISTRICT.test(String(distrito))) {
    return json({ error: "Suscripción inválida" }, 400);
  }
  try {
    const store = await kv();
    const key = await keyFor(sub.endpoint);
    const previous = await store.get(key, "json") as { ultimo_nivel?: string } | null;
    await store.put(key, JSON.stringify({
      sub: { endpoint: sub.endpoint, keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth } },
      distrito,
      creado: new Date().toISOString(),
      ultimo_nivel: previous?.ultimo_nivel ?? null,
    }), { expirationTtl: TTL });
    return json({ ok: true });
  } catch {
    return json({ error: "No se pudo guardar" }, 500);
  }
};

export const DELETE: APIRoute = async ({ request }) => {
  let body: any;
  try { body = await readBody(request); } catch { return json({ error: "Solicitud inválida" }, 400); }
  if (!validEndpoint(body?.endpoint)) return json({ error: "Suscripción inválida" }, 400);
  try {
    await (await kv()).delete(await keyFor(body.endpoint));
    return json({ ok: true });
  } catch {
    return json({ error: "No se pudo borrar" }, 500);
  }
};
