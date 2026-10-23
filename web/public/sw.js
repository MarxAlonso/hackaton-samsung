/* Service worker de Alerta Salud Niño.
 * - Funciona sin conexión: guarda las páginas, los datos y los modelos.
 * - Recibe las alertas push y las muestra como notificación.
 * scripts/postbuild.mjs reemplaza VERSION y PRECACHE_URLS al compilar. */
const VERSION = "dev"; // @version
const PRECACHE_URLS = ["/offline/"]; // @precache
const DATA_URLS = ["/data/app.json", "/data/series.json"];
const STATIC = `static-${VERSION}`;
const DATA = "datos-v1";
const MODELS = "modelos-v1";
const PREFS = "prefs-v1";

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const put = async (cacheName, urls) => {
      const cache = await caches.open(cacheName);
      // uno por uno: si falla un archivo, el resto igual se guarda
      await Promise.allSettled(urls.map(async (url) => {
        const res = await fetch(url, { cache: "reload" });
        if (res.ok) await cache.put(url, res);
      }));
    };
    await put(STATIC, PRECACHE_URLS);
    await put(DATA, DATA_URLS);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith("static-") && key !== STATIC) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

const withTimeout = (promise, ms) =>
  Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms))]);

async function cacheFirst(req, cacheName) {
  const hit = await caches.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) (await caches.open(cacheName)).put(req, res.clone());
  return res;
}

async function networkFirst(req, cacheName, ms) {
  try {
    const res = await withTimeout(fetch(req), ms);
    if (res.ok) (await caches.open(cacheName)).put(req, res.clone());
    return res;
  } catch {
    const hit = await caches.match(req);
    if (hit) return hit;
    throw new Error("sin conexión y sin copia guardada");
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  const fresh = fetch(req).then((res) => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => null);
  return hit || (await fresh) || Response.error();
}

async function navigate(req) {
  try {
    const res = await withTimeout(fetch(req), 4000);
    if (res.ok && !res.redirected && res.type === "basic") (await caches.open(STATIC)).put(req, res.clone());
    return res;
  } catch {
    const url = new URL(req.url);
    const withSlash = new URL(url.pathname.replace(/\/?$/, "/"), url.origin);
    return (await caches.match(req, { ignoreSearch: true }))
      || (await caches.match(withSlash, { ignoreSearch: true }))
      || (await caches.match("/offline/"))
      || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (req.mode === "navigate") return event.respondWith(navigate(req));
  if (url.pathname.startsWith("/data/")) return event.respondWith(networkFirst(req, DATA, 4000));
  if (url.pathname.startsWith("/models/")) return event.respondWith(cacheFirst(req, MODELS));
  if (url.pathname.startsWith("/_astro/") || url.pathname.startsWith("/icons/") || url.pathname === "/manifest.webmanifest") {
    return event.respondWith(cacheFirst(req, STATIC));
  }
  event.respondWith(staleWhileRevalidate(req, STATIC));
});

/* ---------- Alertas push ---------- */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(self.registration.showNotification(data.title || "Alerta Salud Niño", {
    body: data.body || "Hay novedades de salud en tu distrito.",
    icon: "/icons/icon-192.png",
    badge: "/icons/badge-96.png",
    tag: data.tag || "alerta-salud-nino",
    renotify: true,
    lang: "es",
    data: { url: data.url || "/ciudadano/" },
    requireInteraction: data.nivel === "alto",
    actions: [{ action: "abrir", title: "Ver qué hacer" }],
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/ciudadano/", self.location.origin).href;
  event.waitUntil((async () => {
    const open = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of open) {
      if (client.url.startsWith(self.location.origin) && "focus" in client) {
        await client.focus();
        if ("navigate" in client) await client.navigate(target);
        return;
      }
    }
    await self.clients.openWindow(target);
  })());
});

/* Si el navegador renueva la suscripción, se vuelve a registrar sola con el distrito guardado */
const urlB64ToBytes = (b64) => {
  const raw = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil((async () => {
    const saved = await (await caches.open(PREFS)).match("/__prefs");
    if (!saved) return;
    const { distrito, clave } = await saved.json();
    const sub = await self.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToBytes(clave) });
    await fetch("/api/alertas", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ suscripcion: sub.toJSON(), distrito }) });
  })());
});
