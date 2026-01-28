from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Sum
from django.http import HttpResponse
from datetime import date
from decimal import Decimal

from .models import FacturaRegistrada
from .forms import FacturaRegistradaForm

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