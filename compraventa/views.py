from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
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

# ==========================================================
# 🏠 HOME COMPRA-VENTA
# ==========================================================
@login_required
def compraventa_home(request):
    proveedores = Proveedor.objects.all().order_by("nombre_empresa")
    return render(
        request,
        "compraventa/home.html",
        {
            "proveedores": proveedores
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
        monto_total = request.POST.get("monto_total", "").replace(".", "").replace(",", ".")
        
        try:
            from decimal import Decimal, InvalidOperation
            deuda.monto_total = Decimal(monto_total)
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