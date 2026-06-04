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

    ncols = len(columnas) or 1

    # Estilos de celda. Usamos Paragraph para que el texto AJUSTE (wrap)
    # dentro de su columna y nunca se encime con la de al lado.
    head_sty = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10,
                              leading=12.5, textColor=colors.white)
    head_sty_r = ParagraphStyle("hr", parent=head_sty, alignment=2)
    cell_sty = ParagraphStyle("c", fontName="Helvetica", fontSize=9.5, leading=12)
    cell_sty_r = ParagraphStyle("cr", parent=cell_sty, alignment=2)
    tot_sty = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=10.5, leading=13)
    tot_sty_r = ParagraphStyle("tr", parent=tot_sty, alignment=2)

    def fila_par(valores, sty_norm, sty_right):
        out = []
        for i, val in enumerate(valores):
            out.append(Paragraph(str(val), sty_right if i == ncols - 1 else sty_norm))
        return out

    data = [fila_par(columnas, head_sty, head_sty_r)]
    for f in filas:
        data.append(fila_par(f, cell_sty, cell_sty_r))
    if totales:
        data.append(fila_par(totales, tot_sty, tot_sty_r))

    # Anchos proporcionales: la primera columna un poco más ancha (etiquetas),
    # el resto reparte parejo. Como el texto ajusta, no se desborda.
    total_w = A4[0] - 48
    if ncols == 1:
        col_widths = [total_w]
    else:
        weights = [2.0] + [1.0] * (ncols - 1)
        sw = sum(weights)
        col_widths = [total_w * w / sw for w in weights]

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",  (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
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
