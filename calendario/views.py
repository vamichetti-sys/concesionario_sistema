from django.shortcuts import render
from django.http import JsonResponse, HttpResponse

from vehiculos.models import FichaVehicular
from calendario.models import Evento

from datetime import date
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


# ==========================================================
# 📅 VISTA CALENDARIO
# ==========================================================
def calendario_vencimientos(request):
    return render(request, "calendario/calendario_vencimientos.html")


# ==========================================================
# 📅 API DE EVENTOS (VENCIMIENTOS + TURNOS)
# 👉 Vencimientos: FichaVehicular
# 👉 Turnos: Modelo Evento
# ==========================================================
def api_calendario_vencimientos(request):
    eventos = []

    # ==================================================
    # 🔹 VENCIMIENTOS (DESDE FICHA VEHICULAR)
    # ==================================================
    fichas = (
        FichaVehicular.objects
        .select_related("vehiculo")
        .filter(vehiculo__estado="stock")
    )

    for ficha in fichas:
        vehiculo = ficha.vehiculo
        if not vehiculo:
            continue

        base = f"{vehiculo.marca} {vehiculo.modelo} ({vehiculo.dominio})"

        # VTV
        if ficha.vtv_vencimiento:
            eventos.append({
                "start": ficha.vtv_vencimiento,
                "title": f"Vencimiento VTV – {base}",
                "allDay": True,
            })

        # VERIFICACIÓN
        if ficha.verificacion_vencimiento:
            eventos.append({
                "start": ficha.verificacion_vencimiento,
                "title": f"Vencimiento Verificación – {base}",
                "allDay": True,
            })

        # PATENTES
        if ficha.patentes_vto1:
            eventos.append({
                "start": ficha.patentes_vto1,
                "title": f"Vencimiento Patente – {base}",
                "allDay": True,
            })

        if ficha.patentes_vto2:
            eventos.append({
                "start": ficha.patentes_vto2,
                "title": f"Vencimiento Patente – {base}",
                "allDay": True,
            })

        if ficha.patentes_vto3:
            eventos.append({
                "start": ficha.patentes_vto3,
                "title": f"Vencimiento Patente – {base}",
                "allDay": True,
            })

        if ficha.patentes_vto4:
            eventos.append({
                "start": ficha.patentes_vto4,
                "title": f"Vencimiento Patente – {base}",
                "allDay": True,
            })

        if ficha.patentes_vto5:
            eventos.append({
                "start": ficha.patentes_vto5,
                "title": f"Vencimiento Patente – {base}",
                "allDay": True,
            })

    # ==================================================
    # 🔹 TURNOS (MODELO EVENTO)
    # ==================================================
    turnos = Evento.objects.select_related("vehiculo")

    for evento in turnos:
        if not evento.fecha:
            continue

        eventos.append({
            "start": evento.fecha,
            "title": evento.titulo,
            "allDay": True,
        })

    return JsonResponse(eventos, safe=False)


# ==========================================================
# 📄 PDF MENSUAL DEL CALENDARIO
# ==========================================================
def calendario_pdf_mensual(request, anio, mes):
    eventos_pdf = []

    # ==================================================
    # 🔹 VENCIMIENTOS (FICHA VEHICULAR)
    # ==================================================
    fichas = (
        FichaVehicular.objects
        .select_related("vehiculo")
        .filter(
            vehiculo__estado="stock",
            vehiculo__isnull=False
        )
    )

    for ficha in fichas:
        vehiculo = ficha.vehiculo
        base = f"{vehiculo.marca} {vehiculo.modelo} ({vehiculo.dominio})"

        def agregar(fecha, tipo):
            if fecha and fecha.year == anio and fecha.month == mes:
                eventos_pdf.append({
                    "fecha": fecha,
                    "tipo": tipo,
                    "detalle": base
                })

        agregar(ficha.vtv_vencimiento, "Vencimiento VTV")
        agregar(ficha.verificacion_vencimiento, "Vencimiento Verificación")
        agregar(ficha.patentes_vto1, "Vencimiento Patente")
        agregar(ficha.patentes_vto2, "Vencimiento Patente")
        agregar(ficha.patentes_vto3, "Vencimiento Patente")
        agregar(ficha.patentes_vto4, "Vencimiento Patente")
        agregar(ficha.patentes_vto5, "Vencimiento Patente")

    # ==================================================
    # 🔹 TURNOS (EVENTOS)
    # ==================================================
    turnos = Evento.objects.all()

    for evento in turnos:
        if evento.fecha and evento.fecha.year == anio and evento.fecha.month == mes:
            eventos_pdf.append({
                "fecha": evento.fecha,
                "tipo": "Turno",
                "detalle": evento.titulo
            })

    eventos_pdf.sort(key=lambda x: x["fecha"])

    # ==================================================
    # 📄 ARMADO PDF
    # ==================================================
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="calendario_{mes}_{anio}.pdf"'
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
    elements = []

    AZUL = colors.HexColor("#002855")
    GRIS = colors.HexColor("#F4F6F8")

    elements.append(
        Paragraph(
            f"<b>AMICHETTI AUTOMOTORES</b><br/>"
            f"Calendario – {mes}/{anio}",
            ParagraphStyle(
                "h",
                fontSize=14,
                textColor=AZUL,
                alignment=1
            )
        )
    )

    elements.append(Spacer(1, 20))

    data = [["Fecha", "Tipo", "Detalle"]]

    if eventos_pdf:
        for e in eventos_pdf:
            data.append([
                e["fecha"].strftime("%d/%m/%Y"),
                e["tipo"],
                e["detalle"]
            ])
    else:
        data.append(["—", "—", "No hay eventos para este mes"])

    table = Table(data, colWidths=[90, 140, 280])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            "Documento generado automáticamente desde el sistema.",
            ParagraphStyle(
                "f",
                fontSize=8,
                textColor=colors.grey,
                alignment=1
            )
        )
    )

    doc.build(elements)
    return response
