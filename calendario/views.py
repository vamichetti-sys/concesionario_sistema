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
    eventos = {}

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

        # 🆕 DATOS COMUNES DEL VEHÍCULO
        vehiculo_data = {
            "vehiculo_id": vehiculo.id,
            "vehiculo_info": base,
            "url": f"/vehiculos/ficha-completa/{vehiculo.id}/"  # 🔗 Link a la ficha
        }

        # VTV
        if ficha.vtv_vencimiento:
            event_id = f"vtv-{vehiculo.id}-{ficha.vtv_vencimiento}"
            eventos[event_id] = {
                "id": event_id,
                "start": ficha.vtv_vencimiento,
                "title": f"Vencimiento VTV – {base}",
                "allDay": True,
                "color": "#dc3545",  # 🆕 Color rojo para vencimientos
                **vehiculo_data  # 🆕 Datos del vehículo
            }

        # VERIFICACIÓN
        if ficha.verificacion_vencimiento:
            event_id = f"verificacion-{vehiculo.id}-{ficha.verificacion_vencimiento}"
            eventos[event_id] = {
                "id": event_id,
                "start": ficha.verificacion_vencimiento,
                "title": f"Vencimiento Verificación – {base}",
                "allDay": True,
                "color": "#fd7e14",  # 🆕 Color naranja
                **vehiculo_data
            }

        # PATENTES (simplificado con loop)
        patentes_vtos = [
            (ficha.patentes_vto1, 1),
            (ficha.patentes_vto2, 2),
            (ficha.patentes_vto3, 3),
            (ficha.patentes_vto4, 4),
            (ficha.patentes_vto5, 5),
        ]

        for patente_vto, num in patentes_vtos:
            if patente_vto:
                event_id = f"patente{num}-{vehiculo.id}-{patente_vto}"
                eventos[event_id] = {
                    "id": event_id,
                    "start": patente_vto,
                    "title": f"Vencimiento Patente – {base}",
                    "allDay": True,
                    "color": "#ffc107",  # 🆕 Color amarillo
                    **vehiculo_data
                }

    # ==================================================
    # 🔹 TURNOS (MODELO EVENTO)
    # ==================================================
    turnos = Evento.objects.exclude(
        titulo__icontains="Vencimiento"
    ).select_related("vehiculo")

    for evento in turnos:
        if not evento.fecha:
            continue

        event_id = f"turno-{evento.id}"
        
        # 🆕 AGREGAR DATOS DEL VEHÍCULO SI EXISTE
        evento_data = {
            "id": event_id,
            "start": evento.fecha,
            "title": evento.titulo,
            "allDay": True,
            "color": "#0dcaf0",  # 🆕 Color cyan para turnos
        }
        
        if evento.vehiculo:
            evento_data.update({
                "vehiculo_id": evento.vehiculo.id,
                "vehiculo_info": f"{evento.vehiculo.marca} {evento.vehiculo.modelo} ({evento.vehiculo.dominio})",
                "url": f"/vehiculos/ficha-completa/{evento.vehiculo.id}/"
            })
        
        eventos[event_id] = evento_data

    return JsonResponse(list(eventos.values()), safe=False)


# ==========================================================
# 📄 PDF MENSUAL DEL CALENDARIO
# ==========================================================
def calendario_pdf_mensual(request, anio, mes):
    # 🆕 VALIDACIÓN DEL AÑO Y MES
    try:
        anio = int(anio)
        mes = int(mes)
        if not (2000 <= anio <= 2100 and 1 <= mes <= 12):
            return HttpResponse("Año o mes inválido", status=400)
    except (ValueError, TypeError):
        return HttpResponse("Año o mes inválido", status=400)

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
    turnos = (
        Evento.objects
        .exclude(titulo__icontains="Vencimiento")
        .select_related("vehiculo")  # 🆕 Para optimizar
    )

    for evento in turnos:
        if (
            evento.fecha
            and evento.fecha.year == anio
            and evento.fecha.month == mes
        ):
            eventos_pdf.append({
                "fecha": evento.fecha,
                "tipo": "Turno",
                "detalle": evento.titulo
            })

    # Orden cronológico final
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

    # 🆕 NOMBRE DEL MES
    nombres_meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    nombre_mes = nombres_meses[mes - 1]

    elements.append(
        Paragraph(
            f"<b>AMICHETTI AUTOMOTORES</b><br/>"
            f"Calendario – {nombre_mes} {anio}",
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