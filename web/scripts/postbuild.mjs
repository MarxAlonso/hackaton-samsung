// Después de `astro build`: calcula la lista de archivos que el service worker guarda para
// funcionar sin conexión, y la versión (cambia solo si cambia algún archivo).
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dist = join(dirname(fileURLToPath(import.meta.url)), "..", "dist", "client");
const walk = (dir) => readdirSync(dir).flatMap((f) => {
  const p = join(dir, f);
  return statSync(p).isDirectory() ? walk(p) : [p];
});
const toUrl = (p) => "/" + p.slice(dist.length + 1).split("\\").join("/");
const fileOf = (u) => (u.endsWith("/") ? join(dist, u, "index.html") : join(dist, u));

const pages = ["/", "/ciudadano/", "/autoridad/", "/plan/", "/modelo/", "/construccion/", "/offline/"];
const fixed = ["/manifest.webmanifest", "/icon.svg", "/favicon.svg", "/icons/icon-192.png", "/icons/badge-96.png"];
const assets = existsSync(join(dist, "_astro")) ? walk(join(dist, "_astro")).filter((p) => !p.endsWith(".map")).map(toUrl) : [];
const list = [...pages, ...fixed, ...assets].filter((u) => existsSync(fileOf(u)));

const hash = createHash("sha1");
for (const u of list) hash.update(u).update(readFileSync(fileOf(u)));
const version = hash.digest("hex").slice(0, 10);

const swPath = join(dist, "sw.js");
const before = readFileSync(swPath, "utf8");
const after = before
  .replace(/const VERSION = ".*?"; \/\/ @version/, `const VERSION = "${version}"; // @version`)
  .replace(/const PRECACHE_URLS = .*?; \/\/ @precache/, `const PRECACHE_URLS = ${JSON.stringify(list)}; // @precache`);
if (after === before) throw new Error("No se pudieron inyectar VERSION y PRECACHE_URLS en sw.js");
writeFileSync(swPath, after);

const kb = list.reduce((a, u) => a + statSync(fileOf(u)).size, 0) / 1024;
console.log(`[postbuild] service worker v${version}: ${list.length} archivos (${kb.toFixed(0)} KB) para uso sin conexión`);
