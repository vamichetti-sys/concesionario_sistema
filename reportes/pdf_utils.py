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

    tbl = Table(data, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (-1, 1), (-1, -1), "RIGHT"),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_GRIS]),
    ]
    if totales:
        style += [
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
            ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
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
