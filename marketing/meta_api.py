"""
Pequeño cliente de la Graph API de Meta (Facebook / Instagram).

Usa solo la librería estándar (urllib) para no agregar dependencias.
Todas las funciones devuelven (ok, data|error) y nunca lanzan excepción,
así el resto del sistema sigue funcionando aunque Meta falle o falten tokens.
"""
import json
import urllib.parse
import urllib.request
import urllib.error

from django.conf import settings

GRAPH = "https://graph.facebook.com/v21.0"


def _token():
    return getattr(settings, "META_PAGE_ACCESS_TOKEN", "") or ""


def configurado():
    """True si hay token cargado (mínimo para operar)."""
    return bool(_token())


def _get(path, params):
    params = dict(params or {})
    params["access_token"] = _token()
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode("utf-8"))
        except Exception:
            return False, {"error": str(e)}
    except Exception as e:
        return False, {"error": str(e)}


def _post(path, payload):
    data = dict(payload or {})
    data["access_token"] = _token()
    body = urllib.parse.urlencode(data).encode("utf-8")
    url = f"{GRAPH}/{path}"
    try:
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode("utf-8"))
        except Exception:
            return False, {"error": str(e)}
    except Exception as e:
        return False, {"error": str(e)}


def enviar_mensaje(contacto_id, texto):
    """
    Envía un mensaje de texto al contacto (Messenger o Instagram).
    El endpoint /me/messages sirve para ambas plataformas.
    """
    if not configurado():
        return False, {"error": "Falta configurar META_PAGE_ACCESS_TOKEN"}
    payload = {
        "recipient": json.dumps({"id": contacto_id}),
        "message": json.dumps({"text": texto}),
        "messaging_type": "RESPONSE",
    }
    return _post("me/messages", payload)


def obtener_perfil(contacto_id):
    """Trae nombre (y foto) del contacto, si Meta lo permite."""
    if not configurado():
        return {}
    ok, data = _get(contacto_id, {"fields": "name,profile_pic"})
    if ok:
        return data
    return {}


def obtener_lead(leadgen_id):
    """Trae los datos de un lead a partir de su leadgen_id."""
    if not configurado():
        return {}
    ok, data = _get(leadgen_id, {"fields": "field_data,created_time,form_id"})
    if ok:
        return data
    return {}
