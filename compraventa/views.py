from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from datetime import date
from .models import (
    Proveedor,
    CompraVentaOperacion,
    DeudaProveedor,
    PagoProveedor,
)
from .forms import (
    ProveedorForm,
    CompraOperacionForm,
    PagoProveedorForm,
)
from vehiculos.models import FichaVehicular
from decimal import Decimal, InvalidOperation

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

COLOR_AZUL = colors.HexColor("#002855")
COLOR_GRIS = colors.HexColor("#F4F6F8")
COLOR_NARANJA = colors.HexColor("#FF6C1A")


def _parse_monto(raw):
    """Parsea monto en formato argentino (1.234.567,89) o decimal (1234567.89)."""
    if not raw:
        raise InvalidOperation("Monto vacío")
    s = str(raw).strip().replace("$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return Decimal(s)


# ==========================================================
# 🏠 HOME COMPRA-VENTA
# ==========================================================
@login_required
def compraventa_home(request):
    q = request.GET.get("q", "").strip()

    proveedores = Proveedor.objects.all().order_by("nombre_empresa")
    if q:
        proveedores = proveedores.filter(
            Q(nombre_empresa__icontains=q) |
            Q(cuit__icontains=q) |
            Q(telefono__icontains=q) |
            Q(ciudad__icontains=q)
        )

    # Resumen general
    total_deuda = Decimal("0")
    total_pagado = Decimal("0")
    for p in Proveedor.objects.all():
        for d in p.deudas.all():
            total_deuda += d.monto_total
            total_pagado += d.monto_pagado

    return render(
        request,
        "compraventa/home.html",
        {
            "proveedores": proveedores,
            "query": q,
            "total_deuda": total_deuda,
            "total_pagado": total_pagado,
            "saldo_pendiente": total_deuda - total_pagado,
            "cantidad_proveedores": Proveedor.objects.filter(activo=True).count(),
        }
    )

# ==========================================================
# ➕ CREAR PROVEEDOR
# ==========================================================
@login_required
def proveedor_crear(request):
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, "Proveedor creado correctamente.")
            return redirect("compraventa:proveedor_detalle", proveedor_id=proveedor.id)
    else:
        form = ProveedorForm()
    return render(
        request,
        "compraventa/proveedor_form.html",
        {"form": form}
    )

# ==========================================================
# ✏️ EDITAR PROVEEDOR
# ==========================================================
@login_required
def proveedor_editar(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    if request.method == "POST":
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, "Proveedor actualizado correctamente.")
            return redirect("compraventa:proveedor_detalle", proveedor_id=proveedor.id)
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, "compraventa/proveedor_form.html", {
        "form": form,
        "proveedor": proveedor,
        "editando": True,
    })


# ==========================================================
# 📂 DETALLE PROVEEDOR
# ==========================================================
@login_required
def proveedor_detalle(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    deudas = (
        DeudaProveedor.objects
        .filter(proveedor=proveedor)
        .select_related("vehiculo")
        .prefetch_related("pagos")
        .order_by("-creado")
    )
    return render(
        request,
        "compraventa/proveedor_detalle.html",
        {
            "proveedor": proveedor,
            "deudas": deudas,
        }
    )

# ==========================================================
# 🏢 UNIDADES DEL PROVEEDOR (OPTIMIZADA)
# ==========================================================
@login_required
def proveedor_unidades(request, proveedor_id):
    """
    Pantalla: Unidades (vehículos asociados a la agencia/proveedor).
    Muestra la deuda por cada vehículo.
    """
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    
    operaciones = (
        CompraVentaOperacion.objects
        .filter(proveedor=proveedor, origen=CompraVentaOperacion.ORIGEN_PROVEEDOR)
        .select_related("vehiculo")
        .order_by("-fecha_compra", "-id")
    )
    
    # 🆕 OPTIMIZACIÓN: Traer todas las deudas de una sola vez
    vehiculos_ids = [op.vehiculo.id for op in operaciones if op.vehiculo]
    deudas_dict = {
        d.vehiculo_id: d 
        for d in DeudaProveedor.objects.filter(
            proveedor=proveedor,
            vehiculo_id__in=vehiculos_ids
        )
    }
    
    # Agregar información de deuda a cada operación
    for op in operaciones:
        if not op.vehiculo:
            op.deuda_vehiculo = 0
            op.total_pagado_vehiculo = 0
            continue
            
        deuda = deudas_dict.get(op.vehiculo.id)
        if deuda:
            op.deuda_vehiculo = deuda.saldo
            op.total_pagado_vehiculo = deuda.monto_pagado
        else:
            # Si no existe deuda registrada, la deuda es el precio total
            op.deuda_vehiculo = op.precio_compra or 0
            op.total_pagado_vehiculo = 0
    
    return render(
        request,
        "compraventa/proveedor_unidades.html",
        {
            "proveedor": proveedor,
            "operaciones": operaciones,
        }
    )

# ==========================================================
# 💳 CUENTA CORRIENTE DEL PROVEEDOR
# ==========================================================
@login_required
def proveedor_cuenta_corriente(request, proveedor_id):
    """
    Pantalla: Cuenta Corriente (extracto simple).
    - Deudas (por vehículo)
    - Pagos (asociados a esas deudas)
    No modifica nada: solo lectura y render.
    """
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    deudas = (
        DeudaProveedor.objects
        .filter(proveedor=proveedor)
        .select_related("vehiculo")
        .prefetch_related("pagos")
        .order_by("-creado")
    )
    pagos = (
        PagoProveedor.objects
        .filter(deuda__proveedor=proveedor)
        .select_related("deuda", "deuda__vehiculo")
        .order_by("-fecha", "-id")
    )
    
    # 🆕 USAR MÉTODOS PROPERTY EN VEZ DE CÁLCULOS MANUALES
    total_deuda = sum([d.monto_total or 0 for d in deudas], 0)
    total_pagado = sum([d.monto_pagado for d in deudas], 0)
    saldo_total = sum([d.saldo for d in deudas], 0)
    
    return render(
        request,
        "compraventa/proveedor_cuenta_corriente.html",
        {
            "proveedor": proveedor,
            "deudas": deudas,
            "pagos": pagos,
            "total_deuda": total_deuda,
            "total_pagado": total_pagado,
            "saldo_total": saldo_total,
        }
    )

# ==========================================================
# 🔁 REGISTRAR COMPRA / INGRESO
# ==========================================================
@login_required
@transaction.atomic
def compra_registrar(request, proveedor_id=None):
    """
    Registra una compra/ingreso y automáticamente crea o actualiza
    la deuda por vehículo cuando el origen es PROVEEDOR.
    """
    initial = {}
    if proveedor_id:
        initial["proveedor"] = proveedor_id
        initial["origen"] = CompraVentaOperacion.ORIGEN_PROVEEDOR
    
    if request.method == "POST":
        form = CompraOperacionForm(request.POST)
        if form.is_valid():
            op = form.save()
            
            # ==================================================
            # 🔗 VINCULAR VENDEDOR (AGENCIA) A FICHA VEHICULAR
            # ==================================================
            if op.vehiculo and op.proveedor:
                ficha, _ = FichaVehicular.objects.get_or_create(
                    vehiculo=op.vehiculo
                )
                ficha.vendedor = op.proveedor
                ficha.save()
            
            # ==================================================
            # 🔹 Crear o actualizar deuda si es proveedor
            # ==================================================
            if op.origen == CompraVentaOperacion.ORIGEN_PROVEEDOR and op.proveedor:
                monto_total = op.precio_compra or 0
                deuda, created = DeudaProveedor.objects.get_or_create(
                    proveedor=op.proveedor,
                    vehiculo=op.vehiculo,
                    defaults={"monto_total": monto_total},
                )
                if not created:
                    deuda.monto_total = monto_total
                    deuda.save()
            
            messages.success(
                request,
                "Compra / ingreso registrada correctamente."
            )
            
            if op.proveedor:
                return redirect(
                    "compraventa:proveedor_detalle",
                    proveedor_id=op.proveedor.id
                )
            return redirect("compraventa:home")
    else:
        form = CompraOperacionForm(initial=initial)
    
    return render(
        request,
        "compraventa/compra_form.html",
        {"form": form}
    )

# ==========================================================
# 💰 REGISTRAR PAGO A PROVEEDOR
# ==========================================================
@login_required
@transaction.atomic
def deuda_registrar_pago(request, deuda_id):
    deuda = get_object_or_404(
        DeudaProveedor.objects.select_related("proveedor", "vehiculo"),
        id=deuda_id
    )
    
    if request.method == "POST":
        form = PagoProveedorForm(request.POST)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.deuda = deuda
            
            # 🆕 VALIDACIÓN: El monto no puede superar el saldo
            if pago.monto > deuda.saldo:
                messages.error(
                    request, 
                    f"El monto (${pago.monto}) no puede superar el saldo pendiente (${deuda.saldo})"
                )
                return render(
                    request,
                    "compraventa/pago_form.html",
                    {
                        "deuda": deuda,
                        "form": form,
                    }
                )
            
            pago.save()
            messages.success(request, f"Pago de ${pago.monto} registrado correctamente.")
            return redirect(
                "compraventa:proveedor_cuenta_corriente",
                proveedor_id=deuda.proveedor.id
            )
    else:
        form = PagoProveedorForm()
    
    return render(
        request,
        "compraventa/pago_form.html",
        {
            "deuda": deuda,
            "form": form,
        }
    )

# ==========================================================
# 🗑️ ELIMINAR PROVEEDOR
# ==========================================================
@login_required
def proveedor_eliminar(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    
    # 🆕 VALIDACIÓN: No eliminar si tiene deudas pendientes
    if DeudaProveedor.objects.filter(proveedor=proveedor, monto_total__gt=0).exists():
        messages.error(
            request,
            f"No se puede eliminar a {proveedor.nombre_empresa} porque tiene operaciones registradas. "
            "Considere desactivarlo en lugar de eliminarlo."
        )
        return redirect("compraventa:proveedor_detalle", proveedor_id=proveedor.id)
    
    # 🆕 VALIDACIÓN: No eliminar si tiene vehículos asociados
    if CompraVentaOperacion.objects.filter(proveedor=proveedor).exists():
        messages.error(
            request,
            f"No se puede eliminar a {proveedor.nombre_empresa} porque tiene vehículos asociados."
        )
        return redirect("compraventa:proveedor_detalle", proveedor_id=proveedor.id)
    
    nombre = proveedor.nombre_empresa
    proveedor.delete()
    messages.success(
        request,
        f"Proveedor {nombre} eliminado correctamente."
    )
    return redirect("compraventa:home")
# ==========================================================
# ✏️ EDITAR DEUDA (PRECIO DE COMPRA)
# ==========================================================
@login_required
@transaction.atomic
def deuda_editar(request, deuda_id):
    deuda = get_object_or_404(
        DeudaProveedor.objects.select_related("proveedor", "vehiculo"),
        id=deuda_id
    )
    
    if request.method == "POST":
        monto_raw = request.POST.get("monto_total", "")

        try:
            monto_total = _parse_monto(monto_raw)
            deuda.monto_total = monto_total
            deuda.save()
            messages.success(request, "Precio de compra actualizado correctamente.")
        except (ValueError, InvalidOperation):
            messages.error(request, "El monto ingresado no es válido.")
        
        return redirect(
            "compraventa:proveedor_cuenta_corriente",
            proveedor_id=deuda.proveedor.id
        )
    
    return render(
        request,
        "compraventa/deuda_editar.html",
        {"deuda": deuda}
    )


# ==========================================================
# PDF – DATOS DEL PROVEEDOR
# ==========================================================
@login_required
def proveedor_pdf(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    hoy = date.today()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="proveedor_{proveedor.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elementos = []

    # Header
    header = Table([[
        Paragraph(f"<b>AMICHETTI AUTOMOTORES</b><br/>Ficha de Proveedor", ParagraphStyle("h1", fontSize=14, textColor=colors.white)),
        Paragraph(f"Fecha: {hoy.strftime('%d/%m/%Y')}", ParagraphStyle("h2", fontSize=10, textColor=colors.white, alignment=2)),
    ]], colWidths=[340, 180])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), COLOR_AZUL), ("PADDING", (0, 0), (-1, -1), 14)]))
    elementos.append(header)
    elementos.append(Spacer(1, 20))

    # Datos empresa
    elementos.append(Paragraph("<b>DATOS DE LA EMPRESA</b>", ParagraphStyle("sec", fontSize=12, textColor=COLOR_AZUL, spaceAfter=10)))
    datos_empresa = [
        ["Empresa", proveedor.nombre_empresa],
        ["CUIT", proveedor.cuit],
    ]
    if proveedor.contacto_nombre:
        datos_empresa.append(["Contacto", proveedor.contacto_nombre])
    if proveedor.telefono:
        datos_empresa.append(["Teléfono", proveedor.telefono])
    if proveedor.email:
        datos_empresa.append(["Email", proveedor.email])
    if proveedor.domicilio:
        dir_txt = proveedor.domicilio
        if proveedor.ciudad:
            dir_txt += f", {proveedor.ciudad}"
        datos_empresa.append(["Domicilio", dir_txt])

    t = Table(datos_empresa, colWidths=[120, 400])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS),
    ]))
    elementos.append(t)
    elementos.append(Spacer(1, 20))

    # Datos bancarios
    if proveedor.banco or proveedor.cbu or proveedor.alias_bancario:
        elementos.append(Paragraph("<b>DATOS BANCARIOS</b>", ParagraphStyle("sec2", fontSize=12, textColor=COLOR_AZUL, spaceAfter=10)))
        datos_banco = []
        if proveedor.banco:
            datos_banco.append(["Banco", proveedor.banco])
        if proveedor.cbu:
            datos_banco.append(["CBU", proveedor.cbu])
        if proveedor.alias_bancario:
            datos_banco.append(["Alias", proveedor.alias_bancario])
        if proveedor.titular_cuenta:
            datos_banco.append(["Titular", proveedor.titular_cuenta])

        tb = Table(datos_banco, colWidths=[120, 400])
        tb.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS),
        ]))
        elementos.append(tb)
        elementos.append(Spacer(1, 20))

    # Resumen deuda
    deudas = proveedor.deudas.all()
    total_comprado = sum(d.monto_total for d in deudas)
    total_pagado = sum(d.monto_pagado for d in deudas)
    saldo = total_comprado - total_pagado

    elementos.append(Paragraph("<b>RESUMEN FINANCIERO</b>", ParagraphStyle("sec3", fontSize=12, textColor=COLOR_AZUL, spaceAfter=10)))
    resumen = [
        ["Total comprado", f"$ {total_comprado:,.0f}".replace(",", ".")],
        ["Total pagado", f"$ {total_pagado:,.0f}".replace(",", ".")],
        ["Saldo pendiente", f"$ {saldo:,.0f}".replace(",", ".")],
    ]
    tr = Table(resumen, colWidths=[120, 400])
    tr.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS),
        ("TEXTCOLOR", (-1, -1), (-1, -1), colors.HexColor("#ef4444") if saldo > 0 else colors.HexColor("#10b981")),
        ("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    elementos.append(tr)
    elementos.append(Spacer(1, 30))

    elementos.append(Paragraph("Amichetti Automotores · Rojas, Buenos Aires", ParagraphStyle("f", fontSize=8, textColor=colors.grey, alignment=1)))
    doc.build(elementos)
    return response


# ==========================================================
# PDF – CUENTA CORRIENTE DEL PROVEEDOR
# ==========================================================
@login_required
def proveedor_cuenta_corriente_pdf(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    hoy = date.today()

    deudas = proveedor.deudas.select_related("vehiculo").all()
    pagos = PagoProveedor.objects.filter(deuda__proveedor=proveedor).select_related("deuda__vehiculo").order_by("-fecha")

    total_comprado = sum(d.monto_total for d in deudas)
    total_pagado = sum(d.monto_pagado for d in deudas)
    saldo = total_comprado - total_pagado

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="cuenta_corriente_{proveedor.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elementos = []

    header = Table([[
        Paragraph(f"<b>AMICHETTI AUTOMOTORES</b><br/>Cuenta Corriente – {proveedor.nombre_empresa}", ParagraphStyle("h1", fontSize=14, textColor=colors.white)),
        Paragraph(f"Fecha: {hoy.strftime('%d/%m/%Y')}", ParagraphStyle("h2", fontSize=10, textColor=colors.white, alignment=2)),
    ]], colWidths=[340, 180])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), COLOR_AZUL), ("PADDING", (0, 0), (-1, -1), 14)]))
    elementos.append(header)
    elementos.append(Spacer(1, 16))

    # Resumen
    resumen = Table([["Total comprado", "Total pagado", "Saldo"],
        [f"$ {total_comprado:,.0f}".replace(",", "."), f"$ {total_pagado:,.0f}".replace(",", "."), f"$ {saldo:,.0f}".replace(",", ".")]],
        colWidths=[170, 170, 170])
    resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_GRIS),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#ef4444") if saldo > 0 else colors.HexColor("#10b981")),
    ]))
    elementos.append(resumen)
    elementos.append(Spacer(1, 16))

    # Detalle deudas
    elementos.append(Paragraph("<b>DEUDAS POR VEHÍCULO</b>", ParagraphStyle("sec", fontSize=11, textColor=COLOR_AZUL, spaceAfter=8)))
    data_d = [["Vehículo", "Compra", "Pagado", "Saldo"]]
    for d in deudas:
        v = d.vehiculo
        data_d.append([
            f"{v.marca} {v.modelo} ({v.dominio})" if v else "–",
            f"$ {d.monto_total:,.0f}".replace(",", "."),
            f"$ {d.monto_pagado:,.0f}".replace(",", "."),
            f"$ {d.saldo:,.0f}".replace(",", "."),
        ])
    td = Table(data_d, colWidths=[200, 100, 100, 100])
    td.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_GRIS),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(td)
    elementos.append(Spacer(1, 16))

    # Detalle pagos
    if pagos:
        elementos.append(Paragraph("<b>HISTORIAL DE PAGOS</b>", ParagraphStyle("sec2", fontSize=11, textColor=COLOR_AZUL, spaceAfter=8)))
        data_p = [["Fecha", "Vehículo", "Monto", "Nota"]]
        for p in pagos:
            data_p.append([
                p.fecha.strftime("%d/%m/%Y"),
                f"{p.deuda.vehiculo.marca} {p.deuda.vehiculo.modelo}" if p.deuda.vehiculo else "–",
                f"$ {p.monto:,.0f}".replace(",", "."),
                (p.nota or "–")[:30],
            ])
        tp = Table(data_p, colWidths=[80, 180, 100, 140])
        tp.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_GRIS),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(tp)

    elementos.append(Spacer(1, 30))
    elementos.append(Paragraph("Amichetti Automotores · Rojas, Buenos Aires", ParagraphStyle("f", fontSize=8, textColor=colors.grey, alignment=1)))
    doc.build(elementos)
    return response