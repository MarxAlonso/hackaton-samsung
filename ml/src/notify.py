"""Paso 7 — Envío de alertas push a quienes las activaron en la web.

Corre al final del flujo semanal (GitHub Actions), después de publicar el sitio:
  1. Lee las suscripciones guardadas en Cloudflare KV (API REST). Cada una trae solo la dirección
     técnica del navegador y el distrito: no hay nombre, teléfono ni ubicación.
  2. Según el riesgo de HOY en su distrito (el peor entre enfermedades y lluvias extremas) decide si avisar.
  3. Envía una notificación cifrada con Web Push (VAPID). Las suscripciones vencidas se borran.

Cuándo se avisa (para no cansar a la gente):
  - Riesgo ALTO: cada semana mientras siga alto.
  - Riesgo MEDIO: solo cuando sube a medio (o baja desde alto).
  - Riesgo BAJO: una sola vez, cuando baja desde medio o alto ("ya pasó lo peor").

Uso:
  python notify.py                        # producción (variables de entorno, ver abajo)
  python notify.py --dry-run --store-file subs.json   # prueba local sin enviar nada
Variables: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, VAPID_PRIVATE_KEY, [VAPID_SUBJECT].
Si faltan, el paso se omite sin error (así el flujo no falla en repositorios sin alertas).
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import WEB_DATA

API = "https://api.cloudflare.com/client/v4"
SITE = "https://alerta-salud-nino.marxchip99.workers.dev"
KV_TITLES = {"alerta-salud-nino-alertas"}  # nombre que Wrangler le da al binding ALERTAS
KV_TTL = 60 * 60 * 24 * 200
RANK = {"bajo": 0, "medio": 1, "alto": 2}
# Solo servicios de push conocidos (mismo criterio que web/src/pages/api/alertas.ts)
PUSH_HOSTS = [r"(^|\.)googleapis\.com$", r"(^|\.)mozilla\.com$", r"(^|\.)windows\.com$", r"(^|\.)push\.apple\.com$"]


def endpoint_allowed(endpoint: str) -> bool:
    try:
        u = urlparse(endpoint)
    except ValueError:
        return False
    return u.scheme == "https" and any(re.search(p, u.hostname or "") for p in PUSH_HOSTS)


def pct(p: float) -> str:
    return ">99%" if p > 0.99 else "<1%" if p < 0.01 else f"{round(p * 100)}%"


def district_snapshot(app: dict, district_id: str):
    scenario = app["escenarios"]["actual"]
    p = next((d for d in scenario["distritos"] if d["district_id"] == district_id), None)
    if p is None:
        return None
    nivel = max(p["nivel"], p["inundacion"]["nivel"], key=RANK.get)
    return p, nivel


def compose(app: dict, district_id: str):
    """Mensaje de la notificación para un distrito (o None si el distrito no existe)."""
    snap = district_snapshot(app, district_id)
    if snap is None:
        return None
    p, nivel = snap
    name = next(d["district"] for d in app["distritos"] if d["district_id"] == district_id)
    info = app["contenido"]["enfermedades"]
    parts = []
    dengue = p["riesgos"]["dengue"]
    if RANK[dengue["nivel"]] >= 1:
        sufijo = " (estimado con el clima)" if p.get("modelo_tipo") == "clima" else ""
        parts.append(f"dengue: {pct(dengue['prob'])} de probabilidad de brote en 4 semanas{sufijo}")
    for k in p["top_riesgos"]:
        if k != "dengue" and RANK[p["riesgos"][k]["nivel"]] >= 1:
            parts.append(f"{info[k]['nombre'].lower()} en riesgo {p['riesgos'][k]['nivel']}")
            break
    f = p["inundacion"]
    if RANK[f["nivel"]] >= 1:
        when = datetime.date.fromisoformat(f["fecha_max"]).strftime("%d/%m")
        parts.append(f"lluvia de {round(f['lluvia_max_3d_mm'])} mm en 3 días ({when}{', pronosticada' if f['es_pronostico'] else ''})")
    if nivel == "alto":
        title, body = f"Alerta alta en {name}", "; ".join(parts)
    elif nivel == "medio":
        title, body = f"Atención en {name}: riesgo medio", "; ".join(parts)
    else:
        title, body = f"Bajó el riesgo en {name}", "El riesgo de enfermedades y de lluvias extremas bajó. Sigue con la prevención de siempre"
    return {"title": title, "body": f"{body}. Abre la app para ver qué hacer."[:230],
            "url": f"/ciudadano/?d={district_id}&origen=alerta", "tag": f"riesgo-{district_id}", "nivel": nivel}


def should_send(nivel: str, ultimo) -> bool:
    if nivel == "alto":
        return True
    if nivel == "medio":
        return ultimo != "medio"
    return ultimo in ("alto", "medio")


# ---------------------------------------------------------------------------------------------
# Almacenes de suscripciones
# ---------------------------------------------------------------------------------------------
class CloudflareKV:
    def __init__(self, token: str, account: str):
        self.h = {"Authorization": f"Bearer {token}"}
        self.base = f"{API}/accounts/{account}/storage/kv/namespaces"
        r = requests.get(self.base, headers=self.h, params={"per_page": 100}, timeout=30)
        r.raise_for_status()
        found = [n for n in r.json()["result"] if n["title"].lower() in KV_TITLES]
        if not found:
            titles = [n["title"] for n in r.json()["result"]]
            raise RuntimeError(f"No existe el almacén de alertas (busco {sorted(KV_TITLES)}; hay {titles}). Publica el sitio una vez.")
        self.ns = f"{self.base}/{found[0]['id']}"

    def items(self):
        cursor = None
        while True:
            params = {"prefix": "sub:", "limit": 1000, **({"cursor": cursor} if cursor else {})}
            r = requests.get(f"{self.ns}/keys", headers=self.h, params=params, timeout=30)
            r.raise_for_status()
            body = r.json()
            for k in body["result"]:
                v = requests.get(f"{self.ns}/values/{urllib.parse.quote(k['name'], safe='')}", headers=self.h, timeout=30)
                if v.ok:
                    yield k["name"], v.json()
            cursor = (body.get("result_info") or {}).get("cursor")
            if not cursor:
                return

    def put(self, key: str, value: dict):
        r = requests.put(f"{self.ns}/values/{urllib.parse.quote(key, safe='')}", headers={**self.h, "Content-Type": "application/octet-stream"},
                         params={"expiration_ttl": KV_TTL}, data=json.dumps(value).encode(), timeout=30)
        r.raise_for_status()

    def delete(self, key: str):
        requests.delete(f"{self.ns}/values/{urllib.parse.quote(key, safe='')}", headers=self.h, timeout=30)


class FileStore:
    """Para pruebas locales: un JSON {clave: valor}."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def items(self):
        yield from list(self.data.items())

    def put(self, key, value):
        self.data[key] = value
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def delete(self, key):
        self.data.pop(key, None)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------------------------
def send_push(sub: dict, message: dict, vapid_key: str, subject: str, allow_any_endpoint=False):
    from pywebpush import webpush
    if not allow_any_endpoint and not endpoint_allowed(sub["endpoint"]):
        raise ValueError("Dirección de push no permitida")
    webpush(subscription_info=sub, data=json.dumps(message, ensure_ascii=False), vapid_private_key=vapid_key,
            vapid_claims={"sub": subject}, ttl=60 * 60 * 24 * 2, timeout=20,
            headers={"Urgency": "high" if message["nivel"] == "alto" else "normal"})


def run(app: dict, store, vapid_key: str, subject: str, dry_run=False, allow_any_endpoint=False) -> dict:
    stats = {"suscripciones": 0, "enviadas": 0, "omitidas": 0, "eliminadas": 0, "fallidas": 0}
    for key, rec in store.items():
        stats["suscripciones"] += 1
        msg = compose(app, rec.get("distrito", ""))
        if msg is None:
            stats["omitidas"] += 1
            continue
        if not should_send(msg["nivel"], rec.get("ultimo_nivel")):
            stats["omitidas"] += 1
            continue
        if dry_run:
            print(f"  [simulacro] {rec['distrito']}: {msg['title']} — {msg['body']}")
            stats["enviadas"] += 1
            continue
        try:
            send_push(rec["sub"], msg, vapid_key, subject, allow_any_endpoint)
        except Exception as exc:  # WebPushException trae la respuesta HTTP
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):  # el navegador ya no existe o canceló la suscripción
                store.delete(key)
                stats["eliminadas"] += 1
            else:
                stats["fallidas"] += 1
                print(f"  fallo al enviar a {rec.get('distrito')}: {type(exc).__name__} {status or ''}")
            continue
        store.put(key, {**rec, "ultimo_nivel": msg["nivel"], "ultimo_envio": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        stats["enviadas"] += 1
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no envía nada")
    ap.add_argument("--store-file", help="usa un JSON local en vez de Cloudflare KV")
    ap.add_argument("--app-json", default=str(WEB_DATA / "app.json"))
    ap.add_argument("--allow-any-endpoint", action="store_true", help="solo para pruebas locales")
    args = ap.parse_args(argv)

    env = os.environ
    app = json.loads(Path(args.app_json).read_text(encoding="utf-8"))
    vapid = env.get("VAPID_PRIVATE_KEY", "")
    subject = env.get("VAPID_SUBJECT", SITE)
    if args.store_file:
        store = FileStore(args.store_file)
    else:
        missing = [k for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID") if not env.get(k)]
        if missing or (not vapid and not args.dry_run):
            print("Alertas omitidas: faltan " + ", ".join(missing + ([] if vapid else ["VAPID_PRIVATE_KEY"])))
            return 0
        store = CloudflareKV(env["CLOUDFLARE_API_TOKEN"], env["CLOUDFLARE_ACCOUNT_ID"])
    stats = run(app, store, vapid, subject, args.dry_run, args.allow_any_endpoint)
    print("Alertas:", ", ".join(f"{v} {k}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
