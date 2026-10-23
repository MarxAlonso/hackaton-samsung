"""Alertas push: quién recibe aviso, qué dice y que el mensaje llega cifrado y firmado."""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import notify
from config import WEB_DATA

APP = WEB_DATA / "app.json"
pytestmark = pytest.mark.skipif(not APP.exists(), reason="corre ml/run_pipeline.sh primero")


@pytest.fixture(scope="module")
def app():
    return json.loads(APP.read_text(encoding="utf-8"))


def test_cuando_se_avisa():
    assert notify.should_send("alto", None) and notify.should_send("alto", "alto")      # alto: cada semana
    assert notify.should_send("medio", None) and notify.should_send("medio", "alto")     # sube a medio o baja desde alto
    assert not notify.should_send("medio", "medio")                                      # sin repetir
    assert notify.should_send("bajo", "alto") and notify.should_send("bajo", "medio")    # una vez: ya bajó
    assert not notify.should_send("bajo", None) and not notify.should_send("bajo", "bajo")


def test_solo_servicios_de_push_conocidos():
    assert notify.endpoint_allowed("https://fcm.googleapis.com/fcm/send/abc")
    assert notify.endpoint_allowed("https://updates.push.services.mozilla.com/wpush/v2/abc")
    assert notify.endpoint_allowed("https://wns2-pn1p.notify.windows.com/w/?token=abc")
    assert notify.endpoint_allowed("https://web.push.apple.com/abc")
    for bad in ("http://fcm.googleapis.com/x", "https://evil.example.com/x", "https://googleapis.com.evil.io/x", "ftp://x", "no es url"):
        assert not notify.endpoint_allowed(bad), bad


def test_mensaje_de_cada_distrito(app):
    ids = [d["district_id"] for d in app["distritos"]]
    niveles = set()
    for did in ids:
        m = notify.compose(app, did)
        assert m["title"] and m["body"].endswith("Abre la app para ver qué hacer.") or m["nivel"] == "bajo"
        assert len(m["body"]) <= 230 and m["url"].startswith("/ciudadano/?d=" + did)
        niveles.add(m["nivel"])
    assert niveles <= {"alto", "medio", "bajo"}
    assert notify.compose(app, "no-existe") is None


def test_el_mensaje_cita_las_cifras_del_modelo(app):
    for d in app["escenarios"]["actual"]["distritos"]:
        if d["riesgos"]["dengue"]["nivel"] in ("alto", "medio"):
            body = notify.compose(app, d["district_id"])["body"]
            assert "dengue" in body and "%" in body
            return
    pytest.skip("hoy ningún distrito tiene dengue medio o alto")


def test_simulacro_no_envia_ni_modifica(app, tmp_path):
    f = tmp_path / "subs.json"
    f.write_text(json.dumps({"sub:1": {"sub": {"endpoint": "https://fcm.googleapis.com/x", "keys": {}}, "distrito": "piu-castilla", "ultimo_nivel": None}}))
    stats = notify.run(app, notify.FileStore(f), "", notify.SITE, dry_run=True)
    assert stats["suscripciones"] == 1 and stats["fallidas"] == 0
    assert json.loads(f.read_text())["sub:1"]["ultimo_nivel"] is None


class _Receptor(BaseHTTPRequestHandler):
    recibidos = []
    status = 201

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        _Receptor.recibidos.append({"headers": {k.lower(): v for k, v in self.headers.items()}, "body": self.rfile.read(n)})
        self.send_response(_Receptor.status)
        self.end_headers()

    def log_message(self, *a):
        pass


def _subscriber():
    """Un 'navegador' de mentira: par de claves P-256 y secreto de autenticación, como los de una suscripción real."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"
    return priv, auth, {"p256dh": b64(pub), "auth": b64(auth)}


def test_envio_real_cifrado_y_firmado(app, tmp_path):
    """Envía a un receptor local, descifra el cuerpo con las claves del 'navegador' y revisa la firma VAPID."""
    pytest.importorskip("pywebpush")
    import http_ece
    from py_vapid import Vapid01
    from cryptography.hazmat.primitives import serialization

    vapid = Vapid01(); vapid.generate_keys()
    raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    vapid_key = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    # distrito que hoy tenga algún aviso para que el envío no se omita
    did = next(d["district_id"] for d in app["escenarios"]["actual"]["distritos"]
               if notify.compose(app, d["district_id"])["nivel"] != "bajo")
    priv, auth, keys = _subscriber()
    server = HTTPServer(("127.0.0.1", 0), _Receptor)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        store_file = tmp_path / "subs.json"
        store_file.write_text(json.dumps({"sub:x": {"sub": {"endpoint": f"http://127.0.0.1:{server.server_port}/push", "keys": keys},
                                                    "distrito": did, "ultimo_nivel": None}}))
        _Receptor.recibidos.clear()
        stats = notify.run(app, notify.FileStore(store_file), vapid_key, notify.SITE, allow_any_endpoint=True)
    finally:
        server.shutdown()

    assert stats["enviadas"] == 1 and stats["fallidas"] == 0, stats
    req = _Receptor.recibidos[0]
    assert req["headers"]["content-encoding"] == "aes128gcm"
    assert req["headers"]["authorization"].lower().startswith("vapid t=")      # firma VAPID
    plain = http_ece.decrypt(req["body"], private_key=priv, auth_secret=auth, version="aes128gcm")
    msg = json.loads(plain.decode("utf-8"))
    assert msg == notify.compose(app, did)
    # queda registrado el último nivel enviado: la semana siguiente no repite un "medio"
    assert json.loads(store_file.read_text())["sub:x"]["ultimo_nivel"] == msg["nivel"]


def test_suscripcion_vencida_se_elimina(app, tmp_path):
    pytest.importorskip("pywebpush")
    from py_vapid import Vapid01
    vapid = Vapid01(); vapid.generate_keys()
    vapid_key = base64.urlsafe_b64encode(vapid.private_key.private_numbers().private_value.to_bytes(32, "big")).rstrip(b"=").decode()
    did = next(d["district_id"] for d in app["escenarios"]["actual"]["distritos"] if notify.compose(app, d["district_id"])["nivel"] != "bajo")
    _, _, keys = _subscriber()
    _Receptor.status = 410
    server = HTTPServer(("127.0.0.1", 0), _Receptor)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        f = tmp_path / "subs.json"
        f.write_text(json.dumps({"sub:x": {"sub": {"endpoint": f"http://127.0.0.1:{server.server_port}/p", "keys": keys}, "distrito": did, "ultimo_nivel": None}}))
        stats = notify.run(app, notify.FileStore(f), vapid_key, notify.SITE, allow_any_endpoint=True)
    finally:
        _Receptor.status = 201
        server.shutdown()
    assert stats["eliminadas"] == 1 and json.loads(f.read_text()) == {}
