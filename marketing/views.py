import hashlib
import hmac
import json

from django.conf import settings
from django.contrib import messages as dj_messages
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from permisos.access import es_admin

from . import meta_api
from .models import ConversacionMeta, MensajeMeta, LeadMeta


# ==========================================================
# Guard: solo administradores acceden a la parte visual
# ==========================================================
def _solo_admin(request):
    return es_admin(request.user)


# ==========================================================
# WEBHOOK (público) — Meta lo llama para verificar y enviar eventos
# ==========================================================
@csrf_exempt
@login_not_required
def webhook(request):
    # --- Verificación inicial (GET) que pide Meta al configurar ---
    if request.method == "GET":
        modo = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge", "")
        verify = getattr(settings, "META_VERIFY_TOKEN", "")
        if modo == "subscribe" and token and token == verify:
            return HttpResponse(challenge)
        return HttpResponseForbidden("Token de verificación inválido")

    # --- Recepción de eventos (POST) ---
    if request.method == "POST":
        cuerpo = request.body or b""

        # Validación de firma (si hay APP_SECRET configurado)
        secret = getattr(settings, "META_APP_SECRET", "")
        if secret:
            firma = request.headers.get("X-Hub-Signature-256", "")
            esperado = "sha256=" + hmac.new(
                secret.encode(), cuerpo, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(firma, esperado):
                return HttpResponseForbidden("Firma inválida")

        try:
            data = json.loads(cuerpo.decode("utf-8"))
        except Exception:
            return HttpResponse("ok")  # No bloquear a Meta por un body raro

        try:
            _procesar_evento(data)
        except Exception:
            # Nunca devolver error a Meta: reintentaría en loop
            pass
        return HttpResponse("ok")

    return HttpResponse(status=405)


# ==========================================================
# Procesamiento de eventos del webhook
# ==========================================================
def _procesar_evento(data):
    objeto = data.get("object", "")
    plataforma = "instagram" if objeto == "instagram" else "messenger"

    for entry in data.get("entry", []):
        # 1) Mensajes (Messenger / Instagram Direct)
        for ev in entry.get("messaging", []):
            _guardar_mensaje_entrante(ev, plataforma)

        # 2) Cambios (leadgen de Lead Ads, comentarios, etc.)
        for cambio in entry.get("changes", []):
            campo = cambio.get("field", "")
            valor = cambio.get("value", {}) or {}
            if campo == "leadgen":
                _guardar_lead(valor, objeto)


def _guardar_mensaje_entrante(ev, plataforma):
    sender = (ev.get("sender") or {}).get("id")
    msg = ev.get("message") or {}
    if not sender or not msg:
        return
    if msg.get("is_echo"):  # eco de mensajes que enviamos nosotros
        return

    texto = msg.get("text", "") or "[adjunto]"
    mid = msg.get("mid", "")

    conv, _ = ConversacionMeta.objects.get_or_create(
        plataforma=plataforma, contacto_id=sender,
    )
    # Evita duplicados si Meta reintenta el mismo mensaje
    if mid and conv.mensajes.filter(mid=mid).exists():
        return

    # Nombre del contacto (best-effort, solo si todavía no lo tenemos)
    if not conv.nombre:
        perfil = meta_api.obtener_perfil(sender)
        if perfil.get("name"):
            conv.nombre = perfil["name"]
        if perfil.get("profile_pic"):
            conv.foto_url = perfil["profile_pic"]

    MensajeMeta.objects.create(
        conversacion=conv, entrante=True, texto=texto, mid=mid,
        fecha=timezone.now(),
    )
    conv.ultimo_texto = texto
    conv.ultima_fecha = timezone.now()
    conv.no_leido = True
    conv.save()


def _guardar_lead(valor, objeto):
    leadgen_id = valor.get("leadgen_id", "")
    if leadgen_id and LeadMeta.objects.filter(leadgen_id=leadgen_id).exists():
        return

    plataforma = "instagram" if objeto == "instagram" else "facebook"
    detalle = meta_api.obtener_lead(leadgen_id) if leadgen_id else {}

    # field_data = [{"name": "full_name", "values": ["Juan"]}, ...]
    campos = {}
    for f in detalle.get("field_data", []):
        vals = f.get("values") or []
        campos[f.get("name", "")] = vals[0] if vals else ""

    nombre = campos.get("full_name") or campos.get("name") or ""
    telefono = campos.get("phone_number") or campos.get("phone") or ""
    email = campos.get("email") or ""

    lead = LeadMeta.objects.create(
        plataforma=plataforma,
        leadgen_id=leadgen_id,
        form_id=valor.get("form_id", "") or detalle.get("form_id", ""),
        nombre=nombre, telefono=telefono, email=email,
        datos=campos or valor,
    )

    # Crear el prospecto en el CRM
    try:
        from crm.models import Prospecto
        prospecto = Prospecto.objects.create(
            nombre_completo=nombre or "Lead sin nombre",
            telefono=telefono,
            email=email,
            origen=plataforma,  # "instagram" / "facebook" existen en el CRM
            etapa="nuevo",
            observaciones="Lead capturado automáticamente desde Meta.",
        )
        lead.prospecto = prospecto
        lead.save(update_fields=["prospecto"])
    except Exception:
        pass


# ==========================================================
# PANEL (hub del módulo)
# ==========================================================
def panel(request):
    if not _solo_admin(request):
        dj_messages.error(request, "No tenés permiso para acceder a Marketing.")
        return redirect("inicio")

    no_leidos = ConversacionMeta.objects.filter(no_leido=True).count()
    return render(request, "marketing/panel.html", {
        "no_leidos": no_leidos,
        "total_conversaciones": ConversacionMeta.objects.count(),
        "leads_recientes": LeadMeta.objects.all()[:5],
        "total_leads": LeadMeta.objects.count(),
        "conversaciones": ConversacionMeta.objects.all()[:6],
        "conectado": meta_api.configurado(),
    })


# ==========================================================
# BANDEJA (lista de conversaciones)
# ==========================================================
def bandeja(request):
    if not _solo_admin(request):
        return redirect("inicio")
    filtro = request.GET.get("plataforma", "")
    convs = ConversacionMeta.objects.all()
    if filtro in ("instagram", "messenger"):
        convs = convs.filter(plataforma=filtro)
    return render(request, "marketing/bandeja.html", {
        "conversaciones": convs,
        "filtro": filtro,
        "conectado": meta_api.configurado(),
    })


# ==========================================================
# CONVERSACIÓN (hilo + responder)
# ==========================================================
def conversacion(request, pk):
    if not _solo_admin(request):
        return redirect("inicio")
    conv = get_object_or_404(ConversacionMeta, pk=pk)

    if request.method == "POST":
        texto = (request.POST.get("texto") or "").strip()
        if texto:
            ok, resp = meta_api.enviar_mensaje(conv.contacto_id, texto)
            if ok:
                MensajeMeta.objects.create(
                    conversacion=conv, entrante=False, texto=texto,
                    mid=resp.get("message_id", ""), fecha=timezone.now(),
                )
                conv.ultimo_texto = texto
                conv.ultima_fecha = timezone.now()
                conv.save()
            else:
                err = resp.get("error")
                detalle = err.get("message") if isinstance(err, dict) else err
                dj_messages.error(request, f"No se pudo enviar: {detalle}")
        return redirect("marketing:conversacion", pk=conv.pk)

    # Marcar como leída al abrirla
    if conv.no_leido:
        conv.no_leido = False
        conv.save(update_fields=["no_leido"])

    return render(request, "marketing/conversacion.html", {
        "conv": conv,
        "mensajes": conv.mensajes.all(),
        "conectado": meta_api.configurado(),
    })


# ==========================================================
# LEADS
# ==========================================================
def leads(request):
    if not _solo_admin(request):
        return redirect("inicio")
    return render(request, "marketing/leads.html", {
        "leads": LeadMeta.objects.select_related("prospecto").all(),
    })


# ==========================================================
# CONEXIÓN (estado de configuración + datos para Meta)
# ==========================================================
def conexion(request):
    if not _solo_admin(request):
        return redirect("inicio")
    base = getattr(settings, "META_WEBHOOK_BASE_URL", "") or request.build_absolute_uri("/").rstrip("/")
    return render(request, "marketing/conexion.html", {
        "webhook_url": f"{base}/marketing/webhook/",
        "verify_token": getattr(settings, "META_VERIFY_TOKEN", ""),
        "tiene_token": bool(getattr(settings, "META_PAGE_ACCESS_TOKEN", "")),
        "tiene_secret": bool(getattr(settings, "META_APP_SECRET", "")),
        "tiene_verify": bool(getattr(settings, "META_VERIFY_TOKEN", "")),
    })
