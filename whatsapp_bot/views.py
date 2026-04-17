from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q

from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

from vehiculos.models import Vehiculo
import traceback

import os


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")


def buscar_vehiculos(texto):
    """
    Busca vehículos en stock según el texto del usuario.
    Soporta: "amarok", "amarok 2021", "ford", "ford ranger 2022", etc.
    """
    palabras = texto.lower().split()
    qs = Vehiculo.objects.filter(estado="stock")

    for palabra in palabras:
        if palabra.isdigit() and len(palabra) == 4:
            qs = qs.filter(anio=int(palabra))
        else:
            qs = qs.filter(
                Q(marca__icontains=palabra) |
                Q(modelo__icontains=palabra) |
                Q(dominio__icontains=palabra)
            )

    return qs.order_by("marca", "modelo")


def formatear_vehiculo(v, mostrar_precio=False):
    """Formatea los datos de un vehículo para WhatsApp."""
    lineas = [
        f"*{v.marca.upper()} {v.modelo.upper()}*",
        f"Año: {v.anio}",
        f"Dominio: {v.dominio.upper()}",
    ]
    if v.kilometros:
        lineas.append(f"Km: {int(v.kilometros):,}".replace(",", "."))
    if v.es_0km:
        lineas.append("0 KM")
    if mostrar_precio and v.precio:
        lineas.append(f"Precio: ${int(v.precio):,}".replace(",", "."))

    return "\n".join(lineas)


def enviar_fotos_extra(vehiculo, to_number):
    """Envía las fotos extra del vehículo (sin la portada) vía Twilio API."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    portada = vehiculo.fotos.filter(es_portada=True).first() or vehiculo.fotos.first()
    portada_id = portada.id if portada else None

    fotos_extra = vehiculo.fotos.exclude(id=portada_id).order_by("orden")

    for foto in fotos_extra:
        url = foto.imagen.url
        if not url.startswith("http"):
            continue

        client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_FROM}",
            to=to_number,
            media_url=[url],
        )


@csrf_exempt
@require_POST
def webhook(request):
    """Webhook que recibe mensajes de WhatsApp vía Twilio."""
    body = request.POST.get("Body", "").strip()
    from_number = request.POST.get("From", "")

    resp = MessagingResponse()

    if not body:
        resp.message("Enviá el nombre de un vehículo para buscar en nuestro stock.")
        return HttpResponse(str(resp), content_type="text/xml")

    texto = body.lower().strip()

    try:
        return _procesar_mensaje(texto, body, from_number, resp)
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[WHATSAPP BOT ERROR] {error_detail}")
        resp.message(f"Error: {e}")
        return HttpResponse(str(resp), content_type="text/xml")


def _procesar_mensaje(texto, body, from_number, resp):

    # ==========================================================
    # COMANDO: STOCK COMPLETO (paginado para no exceder límite)
    # ==========================================================
    if texto in ("stock", "lista", "todos", "listar"):
        vehiculos = Vehiculo.objects.filter(estado="stock").order_by("marca", "modelo")

        if not vehiculos.exists():
            resp.message("No hay vehículos en stock en este momento.")
            return HttpResponse(str(resp), content_type="text/xml")

        lista_vehiculos = list(vehiculos)
        total = len(lista_vehiculos)

        # Dividir en bloques de 15 para no exceder límite de WhatsApp
        BLOQUE = 15
        for inicio in range(0, total, BLOQUE):
            bloque = lista_vehiculos[inicio:inicio + BLOQUE]

            if inicio == 0:
                lineas = [f"*STOCK ACTUAL ({total} unidades)*\n"]
            else:
                lineas = [f"*... continuación*\n"]

            for i, v in enumerate(bloque, inicio + 1):
                km_txt = f" - {int(v.kilometros):,} km".replace(",", ".") if v.kilometros else ""
                lineas.append(
                    f"{i}. {v.marca.upper()} {v.modelo.upper()} {v.anio} "
                    f"({v.dominio.upper()}){km_txt}"
                )

            if inicio + BLOQUE >= total:
                lineas.append("\nEscribí el nombre o modelo para ver fotos.")
                lineas.append("Escribí *precio* + modelo para ver precios.")

            resp.message("\n".join(lineas))

        return HttpResponse(str(resp), content_type="text/xml")

    # ==========================================================
    # COMANDO: PRECIOS
    # ==========================================================
    if texto.startswith("precio"):
        consulta = texto.replace("precios", "").replace("precio", "").strip()

        if consulta:
            vehiculos = buscar_vehiculos(consulta)
        else:
            vehiculos = Vehiculo.objects.filter(estado="stock").order_by("marca", "modelo")

        if not vehiculos.exists():
            resp.message("No encontré vehículos con esa búsqueda.")
            return HttpResponse(str(resp), content_type="text/xml")

        lista_vehiculos = list(vehiculos)
        BLOQUE = 15
        for inicio in range(0, len(lista_vehiculos), BLOQUE):
            bloque = lista_vehiculos[inicio:inicio + BLOQUE]
            lineas = ["*PRECIOS*\n"] if inicio == 0 else ["*... continuación*\n"]
            for v in bloque:
                precio_txt = f"${int(v.precio):,}".replace(",", ".") if v.precio else "Consultar"
                lineas.append(
                    f"- {v.marca.upper()} {v.modelo.upper()} {v.anio} → {precio_txt}"
                )
            resp.message("\n".join(lineas))

        return HttpResponse(str(resp), content_type="text/xml")

    # ==========================================================
    # COMANDO: AYUDA
    # ==========================================================
    if texto in ("hola", "ayuda", "help", "menu", "menú"):
        resp.message(
            "*Amichetti Automotores - Bot interno*\n\n"
            "Comandos disponibles:\n\n"
            "*stock* → ver todas las unidades\n"
            "*amarok* → buscar por modelo\n"
            "*ford ranger 2022* → búsqueda específica\n"
            "*precio amarok* → ver precio de un modelo\n"
            "*precios* → ver todos los precios\n\n"
            "_Cuando encuentre un vehículo, te envío las fotos._"
        )
        return HttpResponse(str(resp), content_type="text/xml")

    # ==========================================================
    # BÚSQUEDA GENERAL (nombre, modelo, año, dominio)
    # ==========================================================
    vehiculos = buscar_vehiculos(texto)

    if not vehiculos.exists():
        resp.message(
            f"No encontré vehículos con *{body}* en stock.\n\n"
            "Probá con otro nombre, modelo o año.\n"
            "Escribí *stock* para ver todo el listado."
        )
        return HttpResponse(str(resp), content_type="text/xml")

    # Más de 5 resultados: solo lista
    if vehiculos.count() > 5:
        lineas = [f"Encontré *{vehiculos.count()} vehículos* con \"{body}\":\n"]
        for i, v in enumerate(vehiculos, 1):
            km_txt = f" - {int(v.kilometros):,} km".replace(",", ".") if v.kilometros else ""
            lineas.append(
                f"{i}. {v.marca.upper()} {v.modelo.upper()} {v.anio} "
                f"({v.dominio.upper()}){km_txt}"
            )
        lineas.append("\nSé más específico para ver fotos (ej: *amarok 2021*)")
        resp.message("\n".join(lineas))
        return HttpResponse(str(resp), content_type="text/xml")

    # Hasta 5 resultados: datos + foto de portada
    for v in vehiculos:
        msg = resp.message(formatear_vehiculo(v))

        portada = v.fotos.filter(es_portada=True).first() or v.fotos.first()
        if portada and portada.imagen:
            url = portada.imagen.url
            if url.startswith("http"):
                msg.media(url)

    # Si es 1 solo resultado, enviar fotos extra
    if vehiculos.count() == 1:
        v = vehiculos.first()
        if v.fotos.count() > 1:
            enviar_fotos_extra(v, from_number)

    return HttpResponse(str(resp), content_type="text/xml")


def test_bot(request):
    """Vista de prueba para verificar que el bot funciona (acceder desde navegador)."""
    consulta = request.GET.get("q", "stock")
    try:
        if consulta == "stock":
            vehiculos = Vehiculo.objects.filter(estado="stock")
            data = []
            for v in vehiculos:
                fotos_count = v.fotos.count()
                portada = v.fotos.filter(es_portada=True).first()
                data.append({
                    "id": v.id,
                    "marca": v.marca,
                    "modelo": v.modelo,
                    "anio": v.anio,
                    "dominio": v.dominio,
                    "km": v.kilometros,
                    "precio": str(v.precio) if v.precio else None,
                    "fotos": fotos_count,
                    "portada_url": portada.imagen.url if portada else None,
                })
            return JsonResponse({"ok": True, "total": len(data), "vehiculos": data})
        else:
            vehiculos = buscar_vehiculos(consulta)
            return JsonResponse({
                "ok": True,
                "consulta": consulta,
                "total": vehiculos.count(),
                "vehiculos": [
                    {"marca": v.marca, "modelo": v.modelo, "anio": v.anio, "dominio": v.dominio}
                    for v in vehiculos
                ]
            })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e), "trace": traceback.format_exc()})
