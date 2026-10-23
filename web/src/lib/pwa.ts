// PWA: service worker, botón de instalar y alertas push (Web Push estándar: funciona en Chrome,
// Edge, Firefox y Samsung Internet; en iPhone solo con la app instalada, iOS 16.4 o superior).

/** Clave pública VAPID del servidor de alertas (la privada vive solo en los secretos de GitHub). */
export const VAPID_PUBLIC_KEY = "BIARn0u867CZ6ONC8rYOhssqiYJyjwODs7NJ6wvSj01yV0eOT0FZsxOcZs1EdXXi4GolGEZk_R_HkXxmLH1izXk";

export const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches || (navigator as any).standalone === true;
export const isIOS = () =>
  /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
export const pushSupported = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

export async function registerSW(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator) || !import.meta.env.PROD) return null;
  try {
    return await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  } catch (e) {
    console.warn("No se pudo registrar el service worker", e);
    return null;
  }
}

/** Botón "Instalar app": usa el aviso nativo si el navegador lo ofrece; si no, muestra instrucciones. */
export function setupInstall(btn: HTMLButtonElement, dialog: HTMLDialogElement) {
  let deferred: any = null;
  const show = (v: boolean) => { btn.hidden = !v; };
  show(false);
  if (isStandalone()) return;

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e;
    show(true);
  });
  window.addEventListener("appinstalled", () => { deferred = null; show(false); });
  if (isIOS()) show(true); // iPhone no tiene aviso nativo: se explican los pasos

  btn.addEventListener("click", async () => {
    if (deferred) {
      deferred.prompt();
      await deferred.userChoice.catch(() => null);
      deferred = null;
      show(false);
    } else {
      dialog.showModal();
    }
  });
}

export function initPwa() {
  registerSW();
  const btn = document.getElementById("install-btn") as HTMLButtonElement | null;
  const dialog = document.getElementById("install-dialog") as HTMLDialogElement | null;
  if (btn && dialog) setupInstall(btn, dialog);
}

// ---------------------------------------------------------------------------------------------
// Alertas
// ---------------------------------------------------------------------------------------------
function urlBase64ToBytes(b64: string) {
  const raw = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

const PREFS = "prefs-v1";
async function savePrefs(distrito: string | null) {
  const cache = await caches.open(PREFS);
  if (distrito) {
    await cache.put("/__prefs", new Response(JSON.stringify({ distrito, clave: VAPID_PUBLIC_KEY }), { headers: { "content-type": "application/json" } }));
  } else {
    await cache.delete("/__prefs");
  }
}
export async function savedDistrict(): Promise<string | null> {
  try {
    const r = await (await caches.open(PREFS)).match("/__prefs");
    return r ? (await r.json()).distrito : null;
  } catch {
    return null;
  }
}

async function currentSubscription() {
  const reg = await navigator.serviceWorker.ready;
  return { reg, sub: await reg.pushManager.getSubscription() };
}

export type AlertState = { soportado: boolean; permiso: NotificationPermission | "n/d"; activa: boolean; distrito: string | null };

export async function alertState(): Promise<AlertState> {
  if (!pushSupported()) return { soportado: false, permiso: "n/d", activa: false, distrito: null };
  try {
    const { sub } = await currentSubscription();
    return { soportado: true, permiso: Notification.permission, activa: !!sub, distrito: sub ? await savedDistrict() : null };
  } catch {
    return { soportado: true, permiso: Notification.permission, activa: false, distrito: null };
  }
}

export async function enableAlerts(distrito: string): Promise<{ ok: boolean; motivo?: string }> {
  if (!pushSupported()) return { ok: false, motivo: "Tu navegador no admite alertas." };
  const permiso = Notification.permission === "granted" ? "granted" : await Notification.requestPermission();
  if (permiso !== "granted") return { ok: false, motivo: "denegado" };
  const { reg, sub: existing } = await currentSubscription();
  let sub = existing;
  try {
    sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToBytes(VAPID_PUBLIC_KEY) });
  } catch {
    // una suscripción anterior con otra clave bloquea la nueva: se descarta y se reintenta
    await existing?.unsubscribe();
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToBytes(VAPID_PUBLIC_KEY) });
  }
  const r = await fetch("/api/alertas", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ suscripcion: sub.toJSON(), distrito }),
  });
  if (!r.ok) {
    await sub.unsubscribe();
    return { ok: false, motivo: "No pudimos guardar tu suscripción. Intenta de nuevo." };
  }
  await savePrefs(distrito);
  return { ok: true };
}

export async function disableAlerts(): Promise<void> {
  const { sub } = await currentSubscription();
  if (sub) {
    await fetch("/api/alertas", { method: "DELETE", headers: { "content-type": "application/json" }, body: JSON.stringify({ endpoint: sub.endpoint }) }).catch(() => null);
    await sub.unsubscribe();
  }
  await savePrefs(null);
}

/** Muestra una notificación de ejemplo en este mismo dispositivo (no pasa por el servidor). */
export async function showSampleNotification(distrito: string) {
  const reg = await navigator.serviceWorker.ready;
  await reg.showNotification(`Alerta alta en ${distrito}`, {
    body: "Ejemplo: dengue 92% de probabilidad de brote en 4 semanas. Abre la app para ver qué hacer.",
    icon: "/icons/icon-192.png",
    badge: "/icons/badge-96.png",
    tag: "ejemplo",
    lang: "es",
    data: { url: "/ciudadano/" },
  } as NotificationOptions);
}
