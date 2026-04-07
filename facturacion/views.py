from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from datetime import date
from decimal import Decimal

from .models import FacturaRegistrada, CompraRegistrada
from .forms import FacturaRegistradaForm, CompraRegistradaForm

# EXCEL
from openpyxl import Workbook

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


# ==========================================================
# IDENTIDAD VISUAL
# ==========================================================
COLOR_AZUL = colors.HexColor("#002855")
COLOR_NARANJA = colors.HexColor("#FF6C1A")
COLOR_GRIS = colors.HexColor("#F4F6F8")


# ==========================================================
# LISTA FACTURACIÓN
# ==========================================================
@login_required
def lista_facturacion(request):
    facturas = (
        FacturaRegistrada.objects
        .filter(estado="valida")
        .order_by("-fecha")
    )

    hoy = date.today()

    total_mes = (
        FacturaRegistrada.objects
        .filter(
            estado="valida",
            fecha__year=hoy.year,
            fecha__month=hoy.month
        )
        .aggregate(total=Sum("monto"))["total"] or 0
    )

    total_anio = (
        FacturaRegistrada.objects
        .filter(
            estado="valida",
            fecha__year=hoy.year
        )
        .aggregate(total=Sum("monto"))["total"] or 0
    )

    return render(
        request,
        "facturacion/lista.html",
        {
            "page_title": "Facturación",
            "facturas": facturas,
            "total_mes": total_mes,
            "total_anio": total_anio,
        }
    )


# ==========================================================
# CREAR FACTURA
# ==========================================================
@login_required
def crear_factura(request):
    if request.method == "POST":
        form = FacturaRegistradaForm(request.POST)
        if form.is_valid():
            factura = form.save(commit=False)
            # 🔒 Seguridad extra: recalcular IVA
            factura.calcular_iva()
            factura.save()
            return redirect("facturacion:lista")
    else:
        form = FacturaRegistradaForm()

    return render(
        request,
        "facturacion/crear.html",
        {
            "page_title": "Registrar Factura",
            "form": form,
        }
    )


# ==========================================================
# EXPORTAR EXCEL MENSUAL
# ==========================================================
@login_required
def exportar_excel_mensual(request):
    hoy = date.today()

    facturas = FacturaRegistrada.objects.filter(
        estado="valida",
        fecha__year=hoy.year,
        fecha__month=hoy.month
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Facturación Mensual"

    ws.append(["Número", "Fecha", "Monto total", "Venta"])

    for f in facturas:
        ws.append([
            f.numero,
            f.fecha.strftime("%d/%m/%Y"),
            float(f.monto),
            f.venta.id if f.venta else ""
        ])

    total = facturas.aggregate(total=Sum("monto"))["total"] or 0
    ws.append([])
    ws.append(["TOTAL", "", float(total), ""])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="facturacion_{hoy.month}_{hoy.year}.xlsx"'
    )

    wb.save(response)
    return response


# ==========================================================
# EXPORTAR EXCEL ANUAL
# ==========================================================
@login_required
def exportar_excel_anual(request):
    hoy = date.today()

    facturas = FacturaRegistrada.objects.filter(
        estado="valida",
        fecha__year=hoy.year
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Facturación Anual"

    ws.append(["Número", "Fecha", "Monto total", "Venta"])

    for f in facturas:
        ws.append([
            f.numero,
            f.fecha.strftime("%d/%m/%Y"),
            float(f.monto),
            f.venta.id if f.venta else ""
        ])

    total = facturas.aggregate(total=Sum("monto"))["total"] or 0
    ws.append([])
    ws.append(["TOTAL ANUAL", "", float(total), ""])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="facturacion_anual_{hoy.year}.xlsx"'
    )

    wb.save(response)
    return response


# ==========================================================
# EXPORTAR PDF MENSUAL (CON IVA DISCRIMINADO)
# ==========================================================
@login_required
def exportar_pdf_mensual(request):
    hoy = date.today()

    facturas = FacturaRegistrada.objects.filter(
        estado="valida",
        fecha__year=hoy.year,
        fecha__month=hoy.month
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="facturacion_{hoy.month}_{hoy.year}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    elementos = []

    header = Table(
        [[
            Paragraph(
                "<b>AMICHETTI AUTOMOTORES</b><br/>"
                f"Facturación Mensual – {hoy.strftime('%B %Y').capitalize()}",
                ParagraphStyle(
                    "h1",
                    fontSize=14,
                    textColor=colors.white
                )
            ),
            Paragraph(
                f"Fecha emisión<br/>{hoy.strftime('%d/%m/%Y')}",
                ParagraphStyle(
                    "h2",
                    fontSize=10,
                    textColor=colors.white,
                    alignment=2
                )
            )
        ]],
        colWidths=[340, 180]
    )

    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_AZUL),
        ("PADDING", (0, 0), (-1, -1), 14),
    ]))

    elementos.append(header)
    elementos.append(Spacer(1, 20))

    data = [
        ["N° Factura", "Fecha", "Neto", "IVA", "Total"]
    ]

    for f in facturas:
        neto = f.monto_neto if f.monto_neto is not None else f.monto
        iva = f.monto_iva if f.monto_iva is not None else Decimal("0.00")
        total = f.monto

        data.append([
            f.numero,
            f.fecha.strftime("%d/%m/%Y"),
            f"$ {neto:,.2f}",
            f"$ {iva:,.2f}",
            f"$ {total:,.2f}",
        ])

    tabla = Table(data, colWidths=[90, 80, 110, 110, 110])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_GRIS),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 16))

    total_general = facturas.aggregate(total=Sum("monto"))["total"] or 0

    total_box = Table(
        [["TOTAL FACTURADO", f"$ {total_general:,.2f}"]],
        colWidths=[390, 110]
    )

    total_box.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 13),
        ("TEXTCOLOR", (1, 0), (1, 0), COLOR_NARANJA),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))

    elementos.append(total_box)
    elementos.append(Spacer(1, 30))

    elementos.append(
        Paragraph(
            "Amichetti Automotores · Rojas, Buenos Aires",
            ParagraphStyle(
                "f",
                fontSize=8,
                textColor=colors.grey,
                alignment=1
            )
        )
    )

    doc.build(elementos)
    return response


# ==========================================================
# EXPORTAR PDF ANUAL (CON IVA DISCRIMINADO)
# ==========================================================
@login_required
def exportar_pdf_anual(request):
    hoy = date.today()

    facturas = FacturaRegistrada.objects.filter(
        estado="valida",
        fecha__year=hoy.year
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="facturacion_anual_{hoy.year}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    elementos = []

    header = Table(
        [[
            Paragraph(
                "<b>AMICHETTI AUTOMOTORES</b><br/>"
                f"Facturación Anual – {hoy.year}",
                ParagraphStyle(
                    "h1",
                    fontSize=14,
                    textColor=colors.white
                )
            ),
            Paragraph(
                f"Fecha emisión<br/>{hoy.strftime('%d/%m/%Y')}",
                ParagraphStyle(
                    "h2",
                    fontSize=10,
                    textColor=colors.white,
                    alignment=2
                )
            )
        ]],
        colWidths=[340, 180]
    )

    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_AZUL),
        ("PADDING", (0, 0), (-1, -1), 14),
    ]))

    elementos.append(header)
    elementos.append(Spacer(1, 20))

    data = [
        ["N° Factura", "Fecha", "Neto", "IVA", "Total"]
    ]

    for f in facturas:
        neto = f.monto_neto if f.monto_neto is not None else f.monto
        iva = f.monto_iva if f.monto_iva is not None else Decimal("0.00")
        total = f.monto

        data.append([
            f.numero,
            f.fecha.strftime("%d/%m/%Y"),
            f"$ {neto:,.2f}",
            f"$ {iva:,.2f}",
            f"$ {total:,.2f}",
        ])

    tabla = Table(data, colWidths=[90, 80, 110, 110, 110])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_GRIS),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 16))

    total_general = facturas.aggregate(total=Sum("monto"))["total"] or 0

    total_box = Table(
        [["TOTAL ANUAL", f"$ {total_general:,.2f}"]],
        colWidths=[390, 110]
    )

    total_box.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 13),
        ("TEXTCOLOR", (1, 0), (1, 0), COLOR_NARANJA),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))

    elementos.append(total_box)
    elementos.append(Spacer(1, 30))

    elementos.append(
        Paragraph(
            "Amichetti Automotores · Rojas, Buenos Aires",
            ParagraphStyle(
                "f",
                fontSize=8,
                textColor=colors.grey,
                alignment=1
            )
        )
    )

    doc.build(elementos)
    return response

# ==========================================================
# ELIMINAR FACTURA
# ==========================================================
@login_required
def eliminar_factura(request, pk):
    factura = get_object_or_404(FacturaRegistrada, pk=pk)

    if request.method == "POST":
        numero = factura.numero
        factura.delete()
        messages.success(request, f"Factura #{numero} eliminada.")
        return redirect("facturacion:lista")

    return render(request, "facturacion/eliminar.html", {"factura": factura})


# ==========================================================
# COMPRAS - LISTA
# ==========================================================
@login_required
def lista_compras(request):
    hoy = date.today()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    compras = CompraRegistrada.objects.filter(
        fecha__year=anio, fecha__month=mes,
    ).order_by("-fecha")

    total_mes = compras.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    total_iva_mes = compras.aggregate(t=Sum("monto_iva"))["t"] or Decimal("0")

    MESES = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    return render(request, "facturacion/compras.html", {
        "compras": compras,
        "mes": mes,
        "anio": anio,
        "mes_nombre": MESES[mes] if 1 <= mes <= 12 else "",
        "total_mes": total_mes,
        "total_iva_mes": total_iva_mes,
        "meses_choices": list(enumerate(MESES))[1:],
    })


# ==========================================================
# COMPRAS - CREAR
# ==========================================================
@login_required
def crear_compra(request):
    if request.method == "POST":
        form = CompraRegistradaForm(request.POST)
        if form.is_valid():
            compra = form.save(commit=False)
            compra.calcular_iva()
            compra.save()
            messages.success(request, f"Compra #{compra.numero} registrada.")
            return redirect("facturacion:compras")
    else:
        form = CompraRegistradaForm()

    return render(request, "facturacion/crear_compra.html", {
        "form": form,
        "titulo": "Registrar Compra",
    })


# ==========================================================
# COMPRAS - ELIMINAR
# ==========================================================
@login_required
def eliminar_compra(request, pk):
    compra = get_object_or_404(CompraRegistrada, pk=pk)

    if request.method == "POST":
        numero = compra.numero
        compra.delete()
        messages.success(request, f"Compra #{numero} eliminada.")
        return redirect("facturacion:compras")

    return render(request, "facturacion/eliminar_compra.html", {"compra": compra})


# ==========================================================
# IVA - POSICION MENSUAL
# ==========================================================
@login_required
def posicion_iva(request):
    hoy = date.today()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    facturas = FacturaRegistrada.objects.filter(
        estado="valida", fecha__year=anio, fecha__month=mes,
    )
    iva_debito = facturas.aggregate(t=Sum("monto_iva"))["t"] or Decimal("0")
    neto_ventas = facturas.aggregate(t=Sum("monto_neto"))["t"] or Decimal("0")
    total_ventas = facturas.aggregate(t=Sum("monto"))["t"] or Decimal("0")

    compras = CompraRegistrada.objects.filter(
        fecha__year=anio, fecha__month=mes,
    )
    iva_credito = compras.aggregate(t=Sum("monto_iva"))["t"] or Decimal("0")
    neto_compras = compras.aggregate(t=Sum("monto_neto"))["t"] or Decimal("0")
    total_compras = compras.aggregate(t=Sum("monto"))["t"] or Decimal("0")

    saldo_iva = iva_debito - iva_credito

    MESES = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    return render(request, "facturacion/iva.html", {
        "mes": mes,
        "anio": anio,
        "mes_nombre": MESES[mes] if 1 <= mes <= 12 else "",
        "meses_choices": list(enumerate(MESES))[1:],
        "iva_debito": iva_debito,
        "neto_ventas": neto_ventas,
        "total_ventas": total_ventas,
        "facturas_count": facturas.count(),
        "iva_credito": iva_credito,
        "neto_compras": neto_compras,
        "total_compras": total_compras,
        "compras_count": compras.count(),
        "saldo_iva": saldo_iva,
    })
