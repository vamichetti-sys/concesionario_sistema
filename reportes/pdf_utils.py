"""
Helpers para generar PDFs simples de listados/resúmenes mensuales.
Se importan desde otros módulos (cuentas_internas, gastos_personales,
cheques, reportes mismo) para no duplicar el setup de ReportLab.
"""

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
)


COLOR_AZUL = colors.HexColor("#002855")
COLOR_GRIS = colors.HexColor("#f1f5f9")


def render_pdf_listado(
    *,
    filename: str,
    titulo: str,
    subtitulo: str = "",
    columnas: list,
    filas: list,
    totales: list = None,
    pie: str = "",
) -> HttpResponse:
    """
    Arma un PDF tipo 'listado mensual' con un encabezado, una tabla
    de filas, opcionalmente una fila de totales y un pie.

    columnas : list[str]                    — encabezados
    filas    : list[list[str/number]]       — datos
    totales  : list[str] | None             — fila final destacada
    """
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        rightMargin=24, leftMargin=24,
        topMargin=28, bottomMargin=28,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", fontSize=16, textColor=COLOR_AZUL,
        alignment=1, fontName="Helvetica-Bold", spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "subtitle", fontSize=11, alignment=1, spaceAfter=14,
    )
    pie_style = ParagraphStyle(
        "pie", fontSize=9, alignment=1, spaceBefore=12, textColor=colors.grey,
    )

    elements = [
        Paragraph("AMICHETTI AUTOMOTORES", title_style),
        Paragraph(titulo, title_style),
    ]
    if subtitulo:
        elements.append(Paragraph(subtitulo, subtitle_style))
    else:
        elements.append(Spacer(1, 8))

    data = [columnas] + [list(f) for f in filas]
    if totales:
        data.append(list(totales))

    # Anchos que ocupan todo el ancho útil de la página (la primera columna
    # más ancha por ser la etiqueta; el resto reparte lo que queda).
    total_w = A4[0] - 48
    ncols = len(columnas) or 1
    if ncols == 1:
        col_widths = [total_w]
    else:
        first = total_w * 0.5
        rest = (total_w - first) / (ncols - 1)
        col_widths = [first] + [rest] * (ncols - 1)

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10.5),
        ("FONTSIZE",   (0, 1), (-1, -1), 10),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (-1, 1), (-1, -1), "RIGHT"),
        ("LINEBELOW",  (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("LINEAFTER",  (0, 0), (-2, -1), 0.4, colors.HexColor("#eef2f7")),
        ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_GRIS]),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]
    if totales:
        style += [
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
            ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",   (0, -1), (-1, -1), 11),
            ("LINEABOVE",  (0, -1), (-1, -1), 0.8, COLOR_AZUL),
        ]
    tbl.setStyle(TableStyle(style))
    elements.append(tbl)

    if pie:
        elements.append(Paragraph(pie, pie_style))

    doc.build(elements)
    return response


# Meses (1 = enero) — útil para etiquetar PDFs.
MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
