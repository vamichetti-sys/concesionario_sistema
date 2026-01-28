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
# PDF – FALTAS ANUALES POR EMPLEADO
# ==========================================================
@login_required
def pdf_faltas_anuales(request, empleado_id, anio):
    empleado = get_object_or_404(Empleado, id=empleado_id)
    
    # 🆕 VALIDACIÓN DEL AÑO
    try:
        anio = int(anio)
        if anio < 2000 or anio > date.today().year + 1:
            return HttpResponse("Año inválido", status=400)
    except (ValueError, TypeError):
        return HttpResponse("Año inválido", status=400)

    faltas = AsistenciaDiaria.objects.filter(
        empleado=empleado,
        fecha__year=anio,
        estado__in=["falta_injustificada", "falta_justificada"]
    ).order_by("fecha")

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="faltas_{empleado.id}_{anio}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(
        Paragraph("Reporte anual de faltas", styles["Title"])
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(f"<b>Empleado:</b> {empleado.nombre}", styles["Normal"])
    )
    elements.append(
        Paragraph(f"<b>Año:</b> {anio}", styles["Normal"])
    )

    elements.append(Spacer(1, 20))

    data = [["Fecha", "Tipo de falta"]]

    for f in faltas:
        data.append([
            f.fecha.strftime("%d/%m/%Y"),
            f.get_estado_display()
        ])

    if len(data) == 1:
        elements.append(
            Paragraph(
                "El empleado no registra faltas en este año.",
                styles["Normal"]
            )
        )
    else:
        table = Table(data, colWidths=[120, 260])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#002855")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
            ])
        )
        elements.append(table)

    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            f"Total de faltas: <b>{faltas.count()}</b>",
            styles["Normal"]
        )
    )

    doc.build(elements)
    return response