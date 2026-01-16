from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Max, Q
from django.contrib import messages
from django.db import transaction
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

from .models import BoletoCompraventa, Pagare
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
    # 👇 IMPORT LOCAL (FIX DEFINITIVO)
    from weasyprint import HTML
    from io import BytesIO
    from django.core.files.base import ContentFile

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
        print("📩 POST DATA:", request.POST)

        if form.is_valid():
            f = form.cleaned_data
            cliente = f["cliente"]
            vehiculo = f.get("vehiculo")

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

            # ======================================================
            # ARMAR TEXTO LEGAL DEL BOLETO (NO SE TOCA)
            # ======================================================
            texto_final = f"""
Entre el/los Señor/es {cliente.nombre_completo} por una parte como comprador
y el/los Señor/es AMICHETTI HUGO ALBERTO por la otra parte como vendedor,
convienen celebrar el presente boleto de acuerdo a las cláusulas siguientes:

1° - El vendedor vende a {cliente.nombre_completo}un vehículo Marca {f.get("marca", "")}
Modelo {f.get("modelo", "")} Año {f.get("anio", "")} Motor {f.get("motor", "")}
Chasis {f.get("chasis", "")} Dominio {f.get("patente", "")}
en el estado que se encuentra, y que el comprador ha revisado y controlado las
numeraciones de motor, chasis y dominio, aceptando el mismo de conformidad.
2° - El vendedor entrega en este acto toda la documentación referente al vehículo
y el comprador se obliga a realizar la respectiva transferencia dentro de los
treinta (30) días a partir de la fecha.
3° - Los gastos que demande la transferencia del vehículo en el orden nacional, provincial, 
municipal, o de cualquier otro orden serán abonados por el comprado, y lo correspondiente 
a la Ley 21.432/976.-
4° - El comprador deberá asegurar el automotor contra todo riesgo dentro de los dos dias de 
la fecha presente en el boleto, siendo el endoso a favor del vendedor.-
5° - El comprador no podrá vender el vehículo sin autorización expresa del vendedor
hasta no haber abonado la totalidad de la deuda.-
6° - La falta de cumplimiento de cualquiera de las cláusulas del contrato autoriza al 
vendedor a solicitar el inmediato secuestro del vehículo, renunciando el comprador a toda 
defenda en juicio
7° - El vendedor podra optar para el caso en el que el comprador se constituya en mora 
de alguna de las cuotas, por pedir el secuestro judicial de la unidad vendida constituyendo 
el comprador pare el caso de promover accion judicial, domicilio legal en {cliente.direccion or "LARREA 255"}
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

    return render(
        request,
        "boletos/ver.html",
        {
            "boleto": boleto,
            "texto_boleto": texto_boleto
        }
    )

# ==========================================================
# =======================  PAGARÉ  =========================
# ==========================================================

# ====================================
# LISTA + BUSCADOR DE PAGARÉS
# ====================================
def lista_pagares(request):
    q = request.GET.get("q", "").strip()
    pagares = Pagare.objects.select_related("cliente")

    if q:
        pagares = pagares.filter(
            Q(cliente__nombre_completo__icontains=q) |
            Q(cliente__dni_cuit__icontains=q) |
            Q(numero__icontains=q)
        )

    return render(
        request,
        "boletos/pagare/lista.html",
        {"pagares": pagares, "query": q}
    )


# ====================================
# 🔑 PDF LOTE PAGARÉS (UNO DEBAJO DEL OTRO)
# ====================================
def _generar_pdf_lote_pagares_3_por_hoja(pagares):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    ancho, alto = A4
    margen_x = 2 * cm
    y = alto - 2.5 * cm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margen_x, y, "PAGARÉS")
    y -= 1.2 * cm

    c.setFont("Helvetica", 10)

    for idx, pagare in enumerate(pagares, start=1):

        cliente = pagare.cliente
        venc = (
            pagare.fecha_vencimiento.strftime("%d/%m/%Y")
            if pagare.fecha_vencimiento
            else "Pagadero a la vista"
        )

        lineas = [
            f"PAGARÉ Nº {pagare.numero}",
            f"Beneficiario: {pagare.beneficiario}",
            f"Monto: $ {pagare.monto:,.2f}",
            f"Lugar y fecha de emisión: {pagare.lugar_emision}, {pagare.fecha_emision.strftime('%d/%m/%Y')}",
            f"Fecha de vencimiento: {venc}",
            f"Deudor: {cliente.nombre_completo}",
            f"DNI/CUIT: {cliente.dni_cuit or ''}",
        ]

        for linea in lineas:
            if y < 3 * cm:
                c.showPage()
                y = alto - 2.5 * cm
                c.setFont("Helvetica", 10)

            c.drawString(margen_x, y, linea)
            y -= 0.6 * cm

        # SEPARADOR ENTRE PAGARÉS
        if idx < len(pagares):
            y -= 0.3 * cm
            c.setFont("Helvetica", 9)
            c.drawString(margen_x, y, "-" * 90)
            y -= 0.6 * cm
            c.setFont("Helvetica", 10)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ====================================
# CREAR PAGARÉS + PDF (ANTI DOBLE)
# ====================================
@transaction.atomic
def crear_pagares(request):

    if request.method == "POST":

        if request.session.get("generando_pagares"):
            messages.warning(
                request,
                "Los pagarés ya se estaban generando. Se evitó duplicación."
            )
            return redirect("boletos:lista_pagares")

        request.session["generando_pagares"] = True

        try:
            cliente = get_object_or_404(
                Cliente,
                id=request.POST.get("cliente")
            )

            beneficiario = request.POST.get("beneficiario") or "AMICHETTI HUGO ALBERTO"
            lugar_emision = request.POST.get("lugar_emision") or "Rojas"

            fecha_emision = (
                date.fromisoformat(request.POST.get("fecha_emision"))
                if request.POST.get("fecha_emision")
                else date.today()
            )

            cantidad = int(request.POST.get("cantidad", 1))
            ultimo = Pagare.objects.aggregate(max_num=Max("numero")).get("max_num") or 0

            pagares = []

            for i in range(1, cantidad + 1):
                monto = Decimal(request.POST.get(f"monto_{i}", "0"))
                fecha_v = request.POST.get(f"fecha_vencimiento_{i}")
                fecha_v = date.fromisoformat(fecha_v) if fecha_v else None

                pagare = Pagare.objects.create(
                    cliente=cliente,
                    numero=ultimo + i,
                    beneficiario=beneficiario,
                    monto=monto,
                    lugar_emision=lugar_emision,
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_v
                )
                pagares.append(pagare)

            pdf_bytes = _generar_pdf_lote_pagares_3_por_hoja(pagares)

            nombre_cliente = cliente.nombre_completo.strip().replace(" ", "_")
            filename = f"pagares_{nombre_cliente}_{fecha_emision.isoformat()}.pdf"

            pagares[0].pdf.save(filename, ContentFile(pdf_bytes), save=True)

            for p in pagares[1:]:
                p.pdf.name = pagares[0].pdf.name
                p.save(update_fields=["pdf"])

            messages.success(
                request,
                f"✅ Se generaron {cantidad} pagarés en UN solo PDF."
            )

            return redirect("boletos:lista_pagares")

        finally:
            request.session.pop("generando_pagares", None)

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
# PDF PAGARÉ (INDIVIDUAL – NO SE TOCA)
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
    from django.http import HttpResponse
    return HttpResponse(buffer.getvalue(), content_type="application/pdf")
