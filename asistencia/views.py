from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from datetime import date, timedelta

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from .models import Empleado, AsistenciaDiaria
from .forms import EmpleadoForm


# ==========================================================
# LISTA DE EMPLEADOS
# ==========================================================
@login_required
def lista_empleados(request):
    empleados = Empleado.objects.filter(activo=True)

    return render(
        request,
        "asistencia/lista_empleados.html",
        {
            "page_title": "Asistencia",
            "empleados": empleados,
        }
    )


# ==========================================================
# CREAR EMPLEADO
# ==========================================================
@login_required
def crear_empleado(request):
    if request.method == "POST":
        form = EmpleadoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("asistencia:lista")
    else:
        form = EmpleadoForm()

    return render(
        request,
        "asistencia/crear_empleado.html",
        {
            "page_title": "Agregar empleado",
            "form": form,
        }
    )


# ==========================================================
# CALENDARIO ANUAL POR EMPLEADO
# ==========================================================
@login_required
def calendario_empleado(request, empleado_id):
    empleado = get_object_or_404(Empleado, id=empleado_id)

    hoy = date.today()
    try:
        anio = int(request.GET.get("anio", hoy.year))
    except (ValueError, TypeError):
        anio = hoy.year

    asistencias = AsistenciaDiaria.objects.filter(
        empleado=empleado,
        fecha__year=anio
    )

    asistencia_por_fecha = {a.fecha: a.estado for a in asistencias}

    colores = {
        "presente": "#28a745",
        "falta_justificada": "#ffc107",
        "falta_injustificada": "#dc3545",
        "permiso": "#fd7e14",
        "vacaciones": "#0dcaf0",
        "estudio": "#6f42c1",
        None: "#e9ecef",
    }

    calendario = {}

    for mes in range(1, 13):
        dias_mes = []
        primer_dia = date(anio, mes, 1)

        if mes == 12:
            ultimo_dia = date(anio, 12, 31)
        else:
            ultimo_dia = date(anio, mes + 1, 1) - timedelta(days=1)

        dia_actual = primer_dia
        while dia_actual <= ultimo_dia:
            estado = asistencia_por_fecha.get(dia_actual)
            dias_mes.append({
                "fecha": dia_actual,
                "estado": estado,
                "color": colores.get(estado),
            })
            dia_actual += timedelta(days=1)

        calendario[mes] = dias_mes

    resumen_qs = (
        AsistenciaDiaria.objects
        .filter(empleado=empleado, fecha__year=anio)
        .values("estado")
        .annotate(total=models.Count("id"))
    )

    resumen = {r["estado"]: r["total"] for r in resumen_qs}

    return render(
        request,
        "asistencia/calendario_asistencia.html",
        {
            "page_title": f"Asistencia – {empleado.nombre}",
            "empleado": empleado,
            "calendario": calendario,
            "anio": anio,
            "resumen": resumen,
        }
    )


# ==========================================================
# MARCAR / MODIFICAR ASISTENCIA (AJAX)
# ==========================================================
@csrf_exempt
@login_required
def marcar_asistencia(request):
    if request.method == "POST":
        empleado_id = request.POST.get("empleado_id")
        
        # 🆕 VALIDACIÓN
        if not empleado_id:
            return JsonResponse(
                {"ok": False, "error": "ID de empleado requerido"},
                status=400
            )
        
        fecha_str = request.POST.get("fecha")
        estado = request.POST.get("estado")
        observaciones = request.POST.get("observaciones", "")

        fecha = parse_date(fecha_str)
        if not fecha:
            return JsonResponse(
                {"ok": False, "error": "Fecha inválida"},
                status=400
            )

        empleado = get_object_or_404(Empleado, id=empleado_id)

        estados_validos = dict(AsistenciaDiaria.ESTADOS)
        if estado not in estados_validos:
            return JsonResponse(
                {"ok": False, "error": "Estado inválido"},
                status=400
            )

        asistencia, created = AsistenciaDiaria.objects.update_or_create(
            empleado=empleado,
            fecha=fecha,
            defaults={
                "estado": estado,
                "observaciones": observaciones,
            }
        )

        return JsonResponse({
            "ok": True,
            "created": created,
            "estado": asistencia.estado,
        })

    return JsonResponse({"ok": False}, status=400)


# ==========================================================
# PDF – REPORTE ANUAL DE ASISTENCIA POR EMPLEADO
# ==========================================================
@login_required
def pdf_faltas_anuales(request, empleado_id, anio):
    empleado = get_object_or_404(Empleado, id=empleado_id)

    try:
        anio = int(anio)
        if anio < 2000 or anio > date.today().year + 1:
            return HttpResponse("Año inválido", status=400)
    except (ValueError, TypeError):
        return HttpResponse("Año inválido", status=400)

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    # Todas las asistencias del año
    asistencias = AsistenciaDiaria.objects.filter(
        empleado=empleado,
        fecha__year=anio,
    ).order_by("fecha")

    faltas = asistencias.filter(estado__in=["falta_injustificada", "falta_justificada"])

    # Resumen
    from django.db.models import Count
    resumen_qs = asistencias.values("estado").annotate(total=Count("id"))
    resumen = {r["estado"]: r["total"] for r in resumen_qs}

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="asistencia_{empleado.id}_{anio}.pdf"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        rightMargin=35, leftMargin=35,
        topMargin=35, bottomMargin=35,
    )

    styles = getSampleStyleSheet()
    AZUL = colors.HexColor("#002855")
    AZUL_CLARO = colors.HexColor("#dce9f7")

    title_style = ParagraphStyle("title", fontSize=18, textColor=AZUL,
        alignment=1, fontName="Helvetica-Bold", spaceAfter=4)
    subtitle_style = ParagraphStyle("subtitle", fontSize=10, alignment=1,
        textColor=colors.HexColor("#555555"), spaceAfter=16)
    section_style = ParagraphStyle("section", fontSize=11, textColor=colors.white,
        backColor=AZUL, fontName="Helvetica-Bold",
        leftIndent=6, spaceBefore=14, spaceAfter=6)
    normal = styles["Normal"]

    elements = []

    # ── Header ────────────────────────────────────────────
    elements.append(Paragraph("AMICHETTI AUTOMOTORES", title_style))
    elements.append(Paragraph(
        f"Reporte de asistencia &nbsp;|&nbsp; {empleado.nombre} &nbsp;|&nbsp; Año {anio}",
        subtitle_style
    ))

    # ── Resumen ───────────────────────────────────────────
    elements.append(Paragraph("Resumen anual", section_style))

    etiquetas = {
        "presente": "Presente",
        "falta_justificada": "Falta justificada",
        "falta_injustificada": "Falta injustificada",
        "vacaciones": "Vacaciones",
        "estudio": "Día por estudio",
        "permiso": "Permiso",
    }

    resumen_data = [["Estado", "Días"]]
    for key, label in etiquetas.items():
        total = resumen.get(key, 0)
        if total > 0:
            resumen_data.append([label, str(total)])

    if len(resumen_data) == 1:
        resumen_data.append(["Sin registros", "0"])

    resumen_table = Table(resumen_data, colWidths=[doc.width * 0.75, doc.width * 0.25])
    resumen_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(resumen_table)

    # ── Detalle de faltas ─────────────────────────────────
    elements.append(Paragraph("Detalle de faltas", section_style))

    data = [["Fecha", "Tipo de falta"]]
    for f in faltas:
        data.append([f.fecha.strftime("%d/%m/%Y"), f.get_estado_display()])

    if len(data) == 1:
        elements.append(Paragraph("El empleado no registra faltas en este año.", normal))
    else:
        tabla = Table(data, colWidths=[doc.width * 0.3, doc.width * 0.7])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(tabla)

    elements.append(Spacer(1, 14))
    pie_style = ParagraphStyle("pie", fontSize=8,
        textColor=colors.HexColor("#888888"), alignment=1)
    elements.append(Paragraph(
        f"Total de faltas: <b>{faltas.count()}</b> &nbsp;|&nbsp; Registros totales: <b>{asistencias.count()}</b>",
        pie_style
    ))

    doc.build(elements)
    return response