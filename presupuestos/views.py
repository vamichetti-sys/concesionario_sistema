from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse
from decimal import Decimal
from datetime import date, timedelta
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

from .models import Presupuesto
from .forms import PresupuestoForm
from vehiculos.models import Vehiculo


@login_required
def lista_presupuestos(request):
    query = request.GET.get('q', '')
    estado_filtro = request.GET.get('estado', '')

    presupuestos = Presupuesto.objects.select_related('vehiculo', 'cliente', 'vendedor').all()

    if query:
        presupuestos = presupuestos.filter(
            Q(nombre_cliente__icontains=query) |
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query)
        )

    if estado_filtro:
        presupuestos = presupuestos.filter(estado=estado_filtro)

    # Contadores
    total = Presupuesto.objects.count()
    borradores = Presupuesto.objects.filter(estado='borrador').count()
    enviados = Presupuesto.objects.filter(estado='enviado').count()
    aceptados = Presupuesto.objects.filter(estado='aceptado').count()

    return render(request, 'presupuestos/lista.html', {
        'presupuestos': presupuestos,
        'query': query,
        'estado_filtro': estado_filtro,
        'total': total,
        'borradores': borradores,
        'enviados': enviados,
        'aceptados': aceptados,
    })


@login_required
def crear_presupuesto(request):
    if request.method == 'POST':
        form = PresupuestoForm(request.POST)
        if form.is_valid():
            presupuesto = form.save(commit=False)
            
            # Auto-numerar
            ultimo = Presupuesto.objects.order_by('-numero').first()
            presupuesto.numero = (ultimo.numero + 1) if ultimo else 1
            presupuesto.vendedor = request.user
            presupuesto.save()
            
            messages.success(request, f'Presupuesto #{presupuesto.numero} creado.')
            return redirect('presupuestos:detalle', pk=presupuesto.pk)
    else:
        form = PresupuestoForm()

    return render(request, 'presupuestos/form.html', {
        'form': form,
        'titulo': 'Nuevo Presupuesto',
    })


@login_required
def detalle_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    return render(request, 'presupuestos/detalle.html', {
        'p': presupuesto,
    })


@login_required
def editar_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)

    if request.method == 'POST':
        form = PresupuestoForm(request.POST, instance=presupuesto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Presupuesto actualizado.')
            return redirect('presupuestos:detalle', pk=presupuesto.pk)
    else:
        form = PresupuestoForm(instance=presupuesto)

    return render(request, 'presupuestos/form.html', {
        'form': form,
        'titulo': f'Editar Presupuesto #{presupuesto.numero}',
        'presupuesto': presupuesto,
    })


@login_required
def eliminar_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)

    if request.method == 'POST':
        numero = presupuesto.numero
        presupuesto.delete()
        messages.success(request, f'Presupuesto #{numero} eliminado.')
        return redirect('presupuestos:lista')

    return render(request, 'presupuestos/eliminar.html', {
        'presupuesto': presupuesto,
    })


@login_required
def marcar_enviado(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    presupuesto.estado = 'enviado'
    presupuesto.fecha_envio = timezone.now()
    presupuesto.save(update_fields=['estado', 'fecha_envio'])
    messages.success(request, f'Presupuesto #{presupuesto.numero} marcado como enviado.')
    return redirect('presupuestos:detalle', pk=presupuesto.pk)


@login_required
def cambiar_estado(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['borrador', 'enviado', 'aceptado', 'rechazado', 'vencido']:
            presupuesto.estado = nuevo_estado
            if nuevo_estado == 'enviado' and not presupuesto.fecha_envio:
                presupuesto.fecha_envio = timezone.now()
            presupuesto.save()
            messages.success(request, f'Estado actualizado a {nuevo_estado}.')

    return redirect('presupuestos:detalle', pk=presupuesto.pk)


# ==========================================================
# COTIZADOR DE CUOTAS
# ==========================================================
@login_required
def cotizador(request):
    vehiculos = Vehiculo.objects.filter(estado="stock").order_by("marca", "modelo")
    return render(request, "presupuestos/cotizador.html", {
        "vehiculos": vehiculos,
    })


@login_required
def cotizador_pdf(request):
    nombre_cliente = request.GET.get("cliente", "").strip()
    telefono_cliente = request.GET.get("telefono", "").strip()
    vehiculo_id = request.GET.get("vehiculo_id", "")
    precio_raw = request.GET.get("precio", "0").replace(".", "").replace(",", ".")
    anticipo_raw = request.GET.get("anticipo", "0").replace(".", "").replace(",", ".")
    interes_raw = request.GET.get("interes", "0").replace(",", ".")
    cuotas_raw = request.GET.get("cuotas", "1")
    observaciones = request.GET.get("observaciones", "").strip()

    precio = Decimal(precio_raw or "0")
    anticipo = Decimal(anticipo_raw or "0")
    interes = Decimal(interes_raw or "0")
    cantidad_cuotas = int(cuotas_raw or "1")

    monto_financiado = precio - anticipo
    total_interes = monto_financiado * (interes / Decimal("100"))
    total_con_interes = monto_financiado + total_interes
    monto_cuota = total_con_interes / cantidad_cuotas if cantidad_cuotas > 0 else Decimal("0")

    vehiculo = None
    if vehiculo_id:
        try:
            vehiculo = Vehiculo.objects.get(id=vehiculo_id)
        except Vehiculo.DoesNotExist:
            pass

    # Generar PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    AZUL = colors.HexColor("#002855")
    NARANJA = colors.HexColor("#ff6c1a")
    GRIS_CLARO = colors.HexColor("#f8f9fa")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Seccion", fontSize=12, textColor=AZUL, fontName="Helvetica-Bold", spaceAfter=6))

    elements = []

    # HEADER
    header_data = [[
        Paragraph(
            "<font color='white'><b>Amichetti Automotores</b></font><br/>"
            "<font color='#cccccc' size=9>Cotización de financiación</font>",
            ParagraphStyle("H", fontSize=14, textColor=colors.white, fontName="Helvetica-Bold", leading=18)
        ),
        Paragraph(
            f"<font color='white'>Fecha: {date.today().strftime('%d/%m/%Y')}</font>",
            ParagraphStyle("R", fontSize=10, textColor=colors.white, alignment=2, leading=18)
        ),
    ]]
    header_table = Table(header_data, colWidths=[12 * cm, 5 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("LINEBELOW", (0, 0), (-1, -1), 4, NARANJA),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # DATOS DEL CLIENTE
    if nombre_cliente:
        elements.append(Paragraph("Datos del cliente", styles["Seccion"]))
        elements.append(Paragraph(f"Nombre: {nombre_cliente}", styles["Normal"]))
        if telefono_cliente:
            elements.append(Paragraph(f"Teléfono: {telefono_cliente}", styles["Normal"]))
        elements.append(Spacer(1, 14))

    # DATOS DEL VEHÍCULO
    elements.append(Paragraph("Vehículo", styles["Seccion"]))
    if vehiculo:
        elements.append(Paragraph(f"{vehiculo.marca.upper()} {vehiculo.modelo.upper()}", styles["Normal"]))
        elements.append(Paragraph(f"Año: {vehiculo.anio} · Dominio: {vehiculo.dominio.upper()}", styles["Normal"]))
        if vehiculo.kilometros:
            elements.append(Paragraph(f"Kilómetros: {int(vehiculo.kilometros):,} km".replace(",", "."), styles["Normal"]))
    elements.append(Paragraph(f"Precio: ${int(precio):,}".replace(",", "."), styles["Normal"]))
    elements.append(Spacer(1, 14))

    # DETALLE DE FINANCIACIÓN
    elements.append(Paragraph("Detalle de financiación", styles["Seccion"]))

    resumen_data = [
        ["Precio del vehículo", f"$ {int(precio):,}".replace(",", ".")],
        ["Anticipo", f"$ {int(anticipo):,}".replace(",", ".")],
        ["Monto a financiar", f"$ {int(monto_financiado):,}".replace(",", ".")],
        ["Tasa de interés", f"{interes}%"],
        ["Interés total", f"$ {int(total_interes):,}".replace(",", ".")],
        ["Total con interés", f"$ {int(total_con_interes):,}".replace(",", ".")],
        ["Cantidad de cuotas", str(cantidad_cuotas)],
        ["Monto por cuota", f"$ {int(monto_cuota):,}".replace(",", ".")],
    ]

    resumen_table = Table(resumen_data, colWidths=[10 * cm, 7 * cm])
    resumen_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GRIS_CLARO, colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, -1), (-1, -1), 2, NARANJA),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
    ]))
    elements.append(resumen_table)
    elements.append(Spacer(1, 16))

    # TABLA DE CUOTAS
    elements.append(Paragraph("Plan de cuotas", styles["Seccion"]))

    cuotas_data = [["N°", "Vencimiento", "Monto"]]
    fecha_venc = date.today() + timedelta(days=30)
    for i in range(1, cantidad_cuotas + 1):
        cuotas_data.append([
            str(i),
            fecha_venc.strftime("%d/%m/%Y"),
            f"$ {int(monto_cuota):,}".replace(",", "."),
        ])
        fecha_venc += timedelta(days=30)

    cuotas_table = Table(cuotas_data, colWidths=[2 * cm, 8 * cm, 7 * cm])
    cuotas_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("RIGHTPADDING", (2, 0), (2, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
    ]))
    elements.append(cuotas_table)
    elements.append(Spacer(1, 16))

    if observaciones:
        elements.append(Paragraph("Observaciones", styles["Seccion"]))
        elements.append(Paragraph(observaciones, styles["Normal"]))
        elements.append(Spacer(1, 16))

    # PIE
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "<para alignment='center'><font color='#999999' size=8>"
        "Esta cotización es orientativa y no constituye un compromiso de venta. "
        "Sujeta a modificaciones sin previo aviso.<br/>"
        "Amichetti Automotores · Rojas, Buenos Aires · Tel: 2474 660154"
        "</font></para>",
        styles["Normal"]
    ))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    nombre_pdf = f"cotizacion_{nombre_cliente or 'cliente'}".replace(" ", "_").lower()
    response["Content-Disposition"] = f'inline; filename="{nombre_pdf}.pdf"'
    return response