from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Max, Q
from django.utils.timezone import now
from django.contrib import messages
from django.db import transaction
import re
from decimal import Decimal
from datetime import date

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from io import BytesIO

# from weasyprint import HTML

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
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(buffer)
    buffer.seek(0)
    return ContentFile(buffer.read())


# ====================================
# GENERAR PDF BOLETO DESDE HTML (SEGUNDA DEFINICIÓN – NO SE TOCA)
# ====================================
def generar_boleto_pdf_desde_html(request, boleto):

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
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(buffer)
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
            # ARMAR TEXTO LEGAL DEL BOLETO (ACÁ ESTABA EL ERROR)
            # ======================================================
            texto_final = f"""
Entre el/los Señor/es {cliente.nombre_completo} por una parte como comprador
y el/los Señor/es AMICHETTI HUGO ALBERTO por la otra parte como vendedor,
convienen celebrar el presente boleto de acuerdo a las cláusulas siguientes:

1° - El vendedor vende a {cliente.nombre_completo}
un vehículo Marca {f.get("marca", "")}
Modelo {f.get("modelo", "")} Año {f.get("anio", "")} Motor {f.get("motor", "")}
Chasis {f.get("chasis", "")} Dominio {f.get("patente", "")}
en el estado que se encuentra, y que el comprador ha revisado y controlado las
numeraciones de motor, chasis y dominio, aceptando el mismo de conformidad.

2° - El vendedor entrega en este acto toda la documentación referente al vehículo
y el comprador se obliga a realizar la respectiva transferencia dentro de los
treinta (30) días a partir de la fecha.

3° - Los gastos que demande la transferencia del vehículo serán abonados por el comprador.

4° - El comprador deberá asegurar el automotor contra todo riesgo.

5° - El comprador no podrá vender el vehículo sin autorización expresa del vendedor.

6° - La falta de cumplimiento de cualquiera de las cláusulas autoriza al vendedor
a solicitar el inmediato secuestro del vehículo.

7° - Constituyendo el comprador domicilio legal en {cliente.direccion or "LARREA 255"}.

8° - Todos los gastos judiciales que se originen serán a cargo del comprador.

9° - El precio total de la unidad es de {f.get("precio_numeros")}
({f.get("precio_letras")}),
quedando un saldo conforme la siguiente modalidad de pago:
{f.get("saldo_forma_pago")}

LA UNIDAD HA SIDO REVISADA Y ACEPTADA EN CONFORMIDAD.

En la ciudad de ROJAS, a los {date.today().strftime("%d/%m/%Y")}.
"""


            boleto = BoletoCompraventa.objects.create(
                numero=numero,
                cliente=cliente,
                vehiculo=vehiculo,
                cuenta_corriente=cuenta_activa,
                venta=venta,
                texto_final=texto_final
            )

            pdf_file = generar_boleto_pdf_desde_html(request, boleto)
            boleto.pdf.save(
                f"boleto_{boleto.numero}.pdf",
                pdf_file,
                save=True
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
        {"boleto": boleto, "texto_boleto": texto_boleto}
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
# CREAR PAGARÉS + PDF ÚNICO (3 POR HOJA)
# ====================================
@transaction.atomic
def crear_pagares(request):

    if request.method == "POST":

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

        # ===============================
        # CREAR PAGARÉS (SOLO BD)
        # ===============================
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

        # ===============================
        # GENERAR **UN SOLO PDF**
        # ===============================
        pdf_bytes = _generar_pdf_lote_pagares_3_por_hoja(pagares) # type: ignore

        from django.http import HttpResponse
        response = HttpResponse(
            pdf_bytes,
            content_type="application/pdf"
        )

        response["Content-Disposition"] = (
            f'inline; filename="pagares_{cliente.nombre_completo.replace(" ", "_")}.pdf"'
        )

        return response  # 🔴 ACÁ TERMINA TODO

    return render(
        request,
        "boletos/pagare/crear.html",
        {"form": CrearPagareLoteForm()}
    )

# ====================================
# CREAR PAGARÉS + PDF AUTOMÁTICO (ANTI DOBLE EJECUCIÓN)
# ====================================
@transaction.atomic
def crear_pagares(request):

    if request.method == "POST":

        # 🔒 BLOQUEO TOTAL DE DOBLE EJECUCIÓN
        if request.session.get("generando_pagares"):
            messages.warning(
                request,
                "Los pagarés ya se estaban generando. Se evitó una duplicación."
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
            ultimo = (
                Pagare.objects.aggregate(max_num=Max("numero"))
                .get("max_num") or 0
            )

            pagares = []

            # ===============================
            # CREAR PAGARÉS
            # ===============================
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

            # ===============================
            # GENERAR PDF UNA SOLA VEZ
            # ===============================
            pdf_bytes = _generar_pdf_lote_pagares_3_por_hoja(pagares) # type: ignore

            nombre_cliente = cliente.nombre_completo.strip().replace(" ", "_")
            filename = (
                f"pagares_{nombre_cliente}_"
                f"{fecha_emision.isoformat()}_"
                f"{pagares[0].numero}-{pagares[-1].numero}.pdf"
            )

            pagares[0].pdf.save(
                filename,
                ContentFile(pdf_bytes),
                save=True
            )

            pdf_name = pagares[0].pdf.name
            for p in pagares[1:]:
                p.pdf.name = pdf_name
                p.save(update_fields=["pdf"])

            messages.success(
                request,
                f"✅ Se generaron {cantidad} pagarés y el PDF quedó listo para imprimir."
            )

            return redirect("boletos:lista_pagares")

        finally:
            # 🔓 LIBERAR BLOQUEO SIEMPRE
            if "generando_pagares" in request.session:
                del request.session["generando_pagares"]

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
# PDF PAGARÉ (INDIVIDUAL)
# ====================================
def pagare_pdf(request, pagare_id):
    pagare = get_object_or_404(Pagare, id=pagare_id)

    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from django.http import HttpResponse

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