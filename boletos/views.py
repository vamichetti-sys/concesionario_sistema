from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Max, Q
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.conf import settings
import re
from decimal import Decimal
from datetime import date
from io import BytesIO

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

from .models import BoletoCompraventa, Pagare, PagareLote
from .forms import CrearBoletoForm, CrearPagareLoteForm
from clientes.models import Cliente
from cuentas.models import CuentaCorriente


# ====================================
# 🟢 PANEL DE BOLETOS
# ====================================
def panel_boletos(request):
    return render(request, "boletos/panel.html")


# ====================================
# LISTA + BUSCADOR DE BOLETOS
# ====================================
def lista_boletos(request):
    q = request.GET.get("q", "")
    boletos = BoletoCompraventa.objects.all()

    if q:
        boletos = boletos.filter(Q(texto_final__icontains=q))

    return render(
        request,
        "boletos/lista.html",
        {"boletos": boletos, "query": q}
    )


# ====================================
# GENERAR PDF BOLETO DESDE HTML
# ====================================
def generar_boleto_pdf_desde_html(request, boleto):
    from weasyprint import HTML

    cliente = boleto.cliente
    nombre_completo = cliente.nombre_completo or ""
    partes = nombre_completo.strip().split(" ", 1)

    apellido_cliente = partes[0] if partes else ""
    nombre_cliente = partes[1] if len(partes) > 1 else ""

    html_string = render_to_string(
        "boletos/ver.html",
        {
            "boleto": boleto,
            "texto_boleto": boleto.texto_final,
            "vendedor": {
                "apellido": "AMICHETTI",
                "nombre": "HUGO ALBERTO",
                "direccion": "LARREA 255, ROJAS",
                "dni": "13814200",
            },
            "comprador": {
                "apellido": apellido_cliente,
                "nombre": nombre_cliente,
                "direccion": cliente.direccion or "",
                "dni": cliente.dni_cuit or "",
            },
        },
        request=request
    )

    buffer = BytesIO()
    HTML(
        string=html_string,
        base_url=request.build_absolute_uri()
    ).write_pdf(buffer)

    buffer.seek(0)
    return ContentFile(buffer.read())


# ====================================
# CREAR BOLETO
# ====================================
def crear_boleto_manual(request):
    ultimo = BoletoCompraventa.objects.aggregate(
        numero_max=Max("numero")
    )["numero_max"] or 0

    numero = ultimo + 1

    if request.method == "POST":
        form = CrearBoletoForm(request.POST)

        if form.is_valid():
            f = form.cleaned_data
            cliente = f["cliente"]
            vehiculo = f.get("vehiculo")
            
            # 🆕 VALIDACIÓN DE VEHÍCULO
            if not vehiculo:
                messages.error(request, "❌ Debe seleccionar un vehículo.")
                return render(
                    request,
                    "boletos/crear.html",
                    {"form": form, "numero": numero}
                )

            # DATOS COMERCIALES DEL VEHÍCULO
            marca = vehiculo.marca
            modelo = vehiculo.modelo
            anio = vehiculo.anio
            dominio = vehiculo.dominio

            # DATOS REGISTRALES (DESDE LA FICHA VEHICULAR)
            ficha = getattr(vehiculo, "ficha", None)
            motor = getattr(ficha, "numero_motor", "") if ficha else ""
            chasis = getattr(ficha, "numero_chasis", "") if ficha else ""

            if not cliente or not cliente.activo:
                messages.error(request, "❌ Cliente inválido.")
                return render(
                    request,
                    "boletos/crear.html",
                    {"form": form, "numero": numero}
                )

            cuenta_activa = (
                CuentaCorriente.objects
                .filter(cliente=cliente)
                .exclude(estado="cerrada")
                .first()
            )

            venta = (
                cuenta_activa.venta
                if cuenta_activa and hasattr(cuenta_activa, "venta")
                else None
            )

            # ARMAR TEXTO LEGAL DEL BOLETO
            texto_final = f"""
Entre el/los Señor/es {cliente.nombre_completo} por una parte como comprador
y el/los Señor/es AMICHETTI HUGO ALBERTO por la otra parte como vendedor,
convienen celebrar el presente boleto de acuerdo a las cláusulas siguientes:

1° - El vendedor vende a {cliente.nombre_completo} un vehículo Marca {marca}
Modelo {modelo} Año {anio} Motor {motor}
Chasis {chasis} Dominio {dominio} en el estado que se encuentra, y que el comprador 
ha revisado y controlado las numeraciones de motor, chasis y dominio, aceptando el
mismo de conformidad.
2° - El vendedor entrega en este acto toda la documentación referente al vehículo
y el comprador se obliga a realizar la respectiva transferencia dentro de los
treinta (30) días a partir de la fecha.
3° - Los gastos que demande la transferencia del vehículo en el orden nacional, provincial, 
municipal, o de cualquier otro orden serán abonados por el comprador, y lo correspondiente 
a la Ley 21.432/976.-
4° - El comprador deberá asegurar el automotor contra todo riesgo dentro de los dos dias de 
la fecha presente en el boleto, siendo el endoso a favor del vendedor.-
5° - El comprador no podrá vender el vehículo sin autorización expresa del vendedor
hasta no haber abonado la totalidad de la deuda.-
6° - La falta de cumplimiento de cualquiera de las cláusulas del contrato autoriza al 
vendedor a solicitar el inmediato secuestro del vehículo, renunciando el comprador a toda 
defensa en juicio
7° - El vendedor podra optar para el caso en el que el comprador se constituya en mora 
de alguna de las cuotas, por pedir el secuestro judicial de la unidad vendida constituyendo 
el comprador para el caso de promover accion judicial, domicilio legal en {cliente.direccion or "LARREA 255"}
Que asimismo y tambien para el caso de promover acción judicial, queda facultado el vendedor 
a nombrar martillero, comprometiendose el comprador a no poner otra excepcion que la de pago
y renunciando expresamente a la facultad de apelar la resolucion dictada.
8° - Todos los gastos judiciales que se originen serán a cargo del comprador.
9° - El precio total de la unidad es de {f.get("precio_numeros")}({f.get("precio_letras")}),
quedando un saldo conforme la siguiente modalidad de pago: {f.get("saldo_forma_pago")}
10° - La mora en el pago de todas las cuotas convenidas como saldo de precio se producira
por el mero vencimiento de una de ellas, sin necesidad de interpelacion judicial o extra 
judicial de ninguna naturaleza, al producirse dicha mora el deudor perdera automaticamente
a favor del vendedor todo lo abonado hasta esa fecha y la operacion quedara rescindida, 
obligandose al comprador a devolver el vehiculo en ese mismo momento. De no hacerlo asi, 
pagara una multa diaria de acuerdo a los daños y perjuicios ocasionados al vendedor mas toda
otra indemnizacion que por ley correspondiere, pudiendo los vendedores a partir de ese momento
disponer del vehiculo arriba citado. Se deja perfectamente aclarado que este recibo es provisorio, 
debiendo el comprador gestionar directamente ante el titular o ante quien corresponda la transferencia
del vehiculo arriba citado.-
11° - El comprador pagara el 3% para gastos de prenda y el 1% para sellado. El comprador se hace 
responsable civil y criminalmente ante quien corresponda de los daños que ocasionara con este 
vehiculo a partir de la fecha. En fe de cual se firman dos ejemplares de un mismo tenor y a un solo efecto 
En la ciudad de ROJAS, a los {date.today().strftime("%d/%m/%Y")}.

LA UNIDAD HA SIDO REVISADA Y ACEPTADA EN CONFORMIDAD.
"""

            boleto = BoletoCompraventa.objects.create(
                numero=numero,
                cliente=cliente,
                vehiculo=vehiculo,
                cuenta_corriente=cuenta_activa,
                venta=venta,
                texto_final=texto_final
            )

            try:
                pdf_file = generar_boleto_pdf_desde_html(request, boleto)
                boleto.pdf.save(
                    f"boleto_{boleto.numero}.pdf",
                    pdf_file,
                    save=True
                )
            except Exception as e:
                print("❌ ERROR PDF BOLETO:", e)
                messages.warning(
                    request,
                    "⚠️ El boleto se creó correctamente, pero el PDF no pudo generarse."
                )

            messages.success(request, "✅ Boleto generado correctamente")
            return redirect("boletos:ver_boleto", boleto.id)

    return render(
        request,
        "boletos/crear.html",
        {"form": CrearBoletoForm(), "numero": numero}
    )


# ====================================
# VER BOLETO
# ====================================
def ver_boleto(request, boleto_id):
    boleto = get_object_or_404(BoletoCompraventa, id=boleto_id)

    texto_boleto = re.sub(
        r"\n\s*\n+", "\n", (boleto.texto_final or "").strip()
    )

    vendedor = {
        "apellido": "AMICHETTI",
        "nombre": "HUGO ALBERTO",
        "direccion": "LARREA 155",
        "dni": "13814200",
    }

    cliente = boleto.cliente
    nombre_completo = (cliente.nombre_completo or "").strip()
    partes = nombre_completo.split(" ", 1)

    comprador = {
        "apellido": partes[0] if partes else "",
        "nombre": partes[1] if len(partes) > 1 else "",
        "direccion": cliente.direccion or "",
        "dni": cliente.dni_cuit or "",
    }

    return render(
        request,
        "boletos/ver.html",
        {
            "boleto": boleto,
            "texto_boleto": texto_boleto,
            "vendedor": vendedor,
            "comprador": comprador,
        }
    )


# ==========================================================
# =======================  PAGARÉ  =========================
# ==========================================================

def lista_pagares(request):
    q = request.GET.get("q", "").strip()

    lotes = (
        PagareLote.objects
        .select_related("cliente")
        .order_by("-fecha_emision")
    )

    if q:
        lotes = lotes.filter(
            Q(cliente__nombre_completo__icontains=q) |
            Q(cliente__dni_cuit__icontains=q) |
            Q(beneficiario__icontains=q)
        )

    # 🆕 ARMAR URL DEL PDF
    lotes_con_url = []
    for lote in lotes:
        lote_dict = {
            'id': lote.id,
            'cliente': lote.cliente,
            'beneficiario': lote.beneficiario,
            'fecha_emision': lote.fecha_emision,
            'cantidad': lote.cantidad,
            'monto_total': lote.monto_total,
            'pdf_url': lote.pdf.url if lote.pdf else None
        }
        lotes_con_url.append(lote_dict)

    return render(
        request,
        "boletos/pagare/lista.html",
        {
            "lotes": lotes_con_url,
            "query": q,
        }
    )


def monto_en_letras_simple(monto) -> str:
    """
    Devuelve el monto en letras en formato simple y seguro para el pagaré.
    """
    try:
        if monto is None:
            return ""
        if not isinstance(monto, Decimal):
            monto = Decimal(str(monto))
        return f"{monto:,.0f}".replace(",", ".")
    except Exception:
        return str(monto)


def _generar_pdf_lote_pagares_3_por_hoja(pagares):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    ancho, alto = A4
    margen_x = 2 * cm
    POR_HOJA = 3
    contador = 0
    y = alto - 2 * cm

    def fecha_en_letras(fecha):
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        return f"{fecha.day} de {meses[fecha.month - 1]} de {fecha.year}"

    for pagare in pagares:

        # 👉 nueva hoja cada 3 pagarés
        if contador == POR_HOJA:
            c.showPage()
            y = alto - 2 * cm
            contador = 0

        cliente = pagare.cliente

        # =========================
        # TÍTULO
        # =========================
        c.setFont("Helvetica-Bold", 18)
        c.drawString(margen_x, y, "PAGARÉ")
        y -= 0.8 * cm

        c.setFont("Helvetica-Bold", 11)
        c.drawString(
            margen_x,
            y,
            f"Nº {pagare.numero} — Fecha de emisión: {fecha_en_letras(pagare.fecha_emision)}"
        )
        y -= 1 * cm

        # =========================
        # TEXTO LEGAL
        # =========================
        c.setFont("Helvetica", 11)

        if pagare.fecha_vencimiento:
            texto_legal = (
                f"PAGARÉ SIN PROTESTO (Art. 50 D. Ley 5965/63), "
                f"al Sr./a {pagare.beneficiario}, "
                f"la cantidad de PESOS {monto_en_letras_simple(pagare.monto)}, "
                f"el día {fecha_en_letras(pagare.fecha_vencimiento)}."
            )
        else:
            texto_legal = (
                f"PAGARÉ SIN PROTESTO (Art. 50 D. Ley 5965/63), "
                f"al Sr./a {pagare.beneficiario}, "
                f"la cantidad de PESOS {monto_en_letras_simple(pagare.monto)}, "
                f"pagadero a la vista."
            )

        textobject = c.beginText(margen_x, y)
        textobject.setLeading(16)
        max_width = ancho - (2 * margen_x)
        linea_actual = ""

        for palabra in texto_legal.split(" "):
            prueba = linea_actual + palabra + " "
            if c.stringWidth(prueba, "Helvetica", 11) > max_width:
                textobject.textLine(linea_actual.rstrip())
                linea_actual = palabra + " "
            else:
                linea_actual = prueba

        if linea_actual:
            textobject.textLine(linea_actual.rstrip())

        c.drawText(textobject)
        y = textobject.getY() - 0.8 * cm

        # =========================
        # DATOS DEL DEUDOR
        # =========================
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margen_x, y, "Datos del Deudor:")
        y -= 0.6 * cm

        c.setFont("Helvetica", 11)
        c.drawString(margen_x, y, f"Nombre: {cliente.nombre_completo}")
        y -= 0.6 * cm
        c.drawString(margen_x, y, f"DNI/CUIT: {cliente.dni_cuit or ''}")
        y -= 0.6 * cm
        c.drawString(margen_x, y, f"Domicilio: {cliente.direccion or ''}")
        y -= 1.2 * cm

        # =========================
        # FIRMA
        # =========================
        c.drawString(margen_x, y, "Firma: _________________________________")
        y -= 1.5 * cm

        # =========================
        # LÍNEA DE CORTE
        # =========================
        if contador < POR_HOJA - 1:
            c.setDash(3, 3)
            c.line(margen_x, y, ancho - margen_x, y)
            c.setDash()
            y -= 1.2 * cm

        contador += 1

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ====================================
# CREAR PAGARÉS + PDF
# ====================================
@transaction.atomic
def crear_pagares(request):
    if request.method == "POST":
        # ANTI DOBLE ENVÍO
        if request.session.get("generando_pagares"):
            messages.warning(
                request,
                "Los pagarés ya se estaban generando. Se evitó duplicación."
            )
            return redirect("boletos:lista_pagares")

        request.session["generando_pagares"] = True

        try:
            # DATOS GENERALES
            cliente = get_object_or_404(
                Cliente,
                id=request.POST.get("cliente")
            )

            beneficiario = (
                request.POST.get("beneficiario")
                or "AMICHETTI HUGO ALBERTO"
            )

            lugar_emision = (
                request.POST.get("lugar_emision")
                or "Rojas"
            )

            fecha_emision = (
                date.fromisoformat(request.POST.get("fecha_emision"))
                if request.POST.get("fecha_emision")
                else date.today()
            )

            cantidad = int(request.POST.get("cantidad", 1))

            # CREAR LOTE
            lote = PagareLote.objects.create(
                cliente=cliente,
                beneficiario=beneficiario,
                lugar_emision=lugar_emision,
                fecha_emision=fecha_emision,
                cantidad=cantidad,
                monto_total=Decimal("0.00"),
            )

            # NUMERACIÓN
            ultimo = (
                Pagare.objects
                .aggregate(max_num=Max("numero"))
                .get("max_num")
                or 0
            )

            # CREAR PAGARÉS
            pagares = []
            monto_total = Decimal("0.00")

            for i in range(1, cantidad + 1):
                monto = Decimal(
                    request.POST.get(f"monto_{i}", "0")
                )

                fecha_v = request.POST.get(
                    f"fecha_vencimiento_{i}"
                )
                fecha_v = (
                    date.fromisoformat(fecha_v)
                    if fecha_v else None
                )

                pagare = Pagare.objects.create(
                    lote=lote,
                    cliente=cliente,
                    numero=ultimo + i,
                    beneficiario=beneficiario,
                    monto=monto,
                    lugar_emision=lugar_emision,
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_v
                )

                pagares.append(pagare)
                monto_total += monto

            # GENERAR PDF DEL LOTE
            pdf_bytes = _generar_pdf_lote_pagares_3_por_hoja(pagares)

            if not pdf_bytes:
                raise ValueError("No se pudo generar el PDF del pagaré.")

            filename = (
                f"pagares_lote_{lote.id}_"
                f"{fecha_emision.isoformat()}.pdf"
            )

            lote.pdf.save(
                filename,
                ContentFile(pdf_bytes),
                save=True
            )

            # ACTUALIZAR TOTALES DEL LOTE
            lote.monto_total = monto_total
            lote.cantidad = len(pagares)
            lote.save(update_fields=["monto_total", "cantidad"])

            messages.success(
                request,
                f"✅ Se creó el lote con {len(pagares)} pagarés en UN solo PDF."
            )

            return redirect("boletos:lista_pagares")

        except Exception as e:
            messages.error(
                request,
                f"❌ Error al crear pagarés: {str(e)}"
            )
            return redirect("boletos:crear_pagares")

        finally:
            request.session.pop("generando_pagares", None)

    # GET
    return render(
        request,
        "boletos/pagare/crear.html",
        {"form": CrearPagareLoteForm()}
    )


# ====================================
# VER PAGARÉ
# ====================================
def ver_pagare(request, pagare_id):
    pagare = get_object_or_404(Pagare, id=pagare_id)
    return render(
        request,
        "boletos/pagare/ver.html",
        {"pagare": pagare}
    )


# ====================================
# PDF PAGARÉ INDIVIDUAL
# ====================================
def pagare_pdf(request, pagare_id):
    pagare = get_object_or_404(Pagare, id=pagare_id)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    azul = colors.HexColor("#002855")
    y = A4[1] - 2.2 * cm

    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(azul)
    c.drawString(2 * cm, y, "PAGARÉ")

    y -= 1 * cm
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Nº {pagare.numero}")

    y -= 1 * cm

    cliente = pagare.cliente
    venc = pagare.fecha_vencimiento.strftime("%d/%m/%Y") if pagare.fecha_vencimiento else "Pagadero a la vista"

    texto = [
        "PAGARÉ SIN PROTESTO A LA ORDEN DE AMICHETTI HUGO ALBERTO",
        "",
        f"Monto: $ {pagare.monto:,.2f}",
        f"Lugar y fecha de emisión: {pagare.lugar_emision}, {pagare.fecha_emision.strftime('%d/%m/%Y')}",
        f"Fecha de vencimiento: {venc}",
        "",
        f"Deudor: {cliente.nombre_completo}",
        f"DNI/CUIT: {cliente.dni_cuit or ''}",
        f"Domicilio: {cliente.direccion or ''}",
        "",
        "Firma: ________________________________",
    ]

    for t in texto:
        c.drawString(2 * cm, y, t)
        y -= 0.7 * cm

    c.showPage()
    c.save()

    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type="application/pdf")