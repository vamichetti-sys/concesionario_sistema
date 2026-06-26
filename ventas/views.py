from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.db import transaction
from django.utils import timezone

from vehiculos.models import Vehiculo
from clientes.models import Cliente
from cuentas.models import (
    CuentaCorriente,
    PlanPago,
    CuotaPlan
)

from gestoria.models import Gestoria
from permisos.views import solo_admin
from .models import Venta, CuentaVendedor, MovimientoComision


# ==========================================================
# HELPERS (NO SACAN FUNCIONES)
# ==========================================================
def _venta_cuenta_field_name():
    field_names = {f.name for f in Venta._meta.get_fields()}
    if "cuenta_corriente" in field_names:
        return "cuenta_corriente"
    if "cuenta" in field_names:
        return "cuenta"
    return None


def _get_venta_cuenta(venta):
    fname = _venta_cuenta_field_name()
    if not fname:
        return None
    return getattr(venta, fname, None)


def _set_venta_cuenta(venta, cuenta_obj):
    fname = _venta_cuenta_field_name()
    if not fname:
        return None
    setattr(venta, fname, cuenta_obj)
    return fname


# ==========================================================
# LISTADO DE UNIDADES VENDIDAS + BUSCADOR
# ==========================================================
def lista_unidades_vendidas(request):
    query = request.GET.get("q", "").strip()
    cuenta_field = _venta_cuenta_field_name()

    related_fields = [
        "vehiculo",
        "cliente",
        "vehiculo__ficha",
        "vendido_por",
    ]
    if cuenta_field:
        related_fields.append(cuenta_field)

    ventas = (
        Venta.objects
        .filter(estado__in=["pendiente", "confirmada"])
        .select_related(*related_fields)
    )

    if query:
        ventas = ventas.filter(
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(cliente__nombre_completo__icontains=query) |
            Q(id__icontains=query)
        ).distinct()

    ventas = ventas.order_by("-id")

    return render(
        request,
        "ventas/lista_unidades_vendidas.html",
        {
            "ventas": ventas,
            "query": query,
        },
    )


# ==========================================================
# PDF: LISTADO DE UNIDADES VENDIDAS
# ==========================================================
def pdf_unidades_vendidas(request):
    from datetime import date
    from decimal import Decimal
    from reportes.pdf_utils import render_pdf_listado

    query = request.GET.get("q", "").strip()
    ventas = (
        Venta.objects
        .filter(estado__in=["pendiente", "confirmada"])
        .select_related("vehiculo", "cliente")
    )
    if query:
        ventas = ventas.filter(
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(cliente__nombre_completo__icontains=query) |
            Q(id__icontains=query)
        ).distinct()
    ventas = ventas.order_by("-id")

    total = Decimal("0")
    filas = []
    for v in ventas:
        total += v.precio_venta or Decimal("0")
        filas.append([
            f"#{v.id}",
            f"{v.vehiculo.marca} {v.vehiculo.modelo}" if v.vehiculo_id else "—",
            v.vehiculo.dominio or "—" if v.vehiculo_id else "—",
            v.cliente.nombre_completo if v.cliente_id else "Sin cliente",
            v.fecha_venta.strftime("%d/%m/%Y") if v.fecha_venta else "—",
            v.get_estado_display(),
            f"$ {(v.precio_venta or 0):,.0f}".replace(",", "."),
        ])

    totales = ["", "", "", "", "", "TOTAL", f"$ {total:,.0f}".replace(",", ".")]

    return render_pdf_listado(
        filename="unidades_vendidas.pdf",
        titulo="Unidades Vendidas",
        subtitulo=(f"Búsqueda: «{query}» – " if query else "") + f"{len(filas)} unidad(es)",
        columnas=["#", "Vehículo", "Dominio", "Cliente", "Fecha", "Estado", "Precio"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {date.today().strftime('%d/%m/%Y')}",
    )


# ==========================================================
# BUSCAR CLIENTE (AJAX)
# ==========================================================
def buscar_cliente_venta(request):
    q = request.GET.get("q", "").strip()

    clientes = (
        Cliente.objects
        .filter(
            Q(nombre_completo__icontains=q) |
            Q(dni_cuit__icontains=q)
        )
        .order_by("nombre_completo")[:10]
    )

    data = [
        {
            "id": c.id,
            "nombre": c.nombre_completo,
            "dni": c.dni_cuit
        }
        for c in clientes
    ]

    return JsonResponse(data, safe=False)


# ==========================================================
# ASIGNAR CLIENTE A VENTA (VINCULACIÓN RESTAURADA)
# ==========================================================
@transaction.atomic
def asignar_cliente_venta(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    venta = get_object_or_404(Venta, vehiculo=vehiculo)

    cuenta_existente = _get_venta_cuenta(venta)

    # 🔒 Solo bloquear si ya está completamente armada
    if venta.cliente and cuenta_existente:
        messages.info(
            request,
            "Esta venta ya tiene cliente y cuenta corriente asociada."
        )
        return redirect("ventas:lista_unidades_vendidas")

    clientes = Cliente.objects.all().order_by("nombre_completo")

    if request.method == "POST":
        cliente_id = request.POST.get("cliente")
        if not cliente_id:
            messages.error(request, "Debes seleccionar un cliente.")
            return redirect("ventas:asignar_cliente", vehiculo_id=vehiculo.id)
        cliente = get_object_or_404(Cliente, id=cliente_id)

        # ==================================================
        # 🔑 ASIGNACIÓN CORRECTA (CENTRALIZADA)
        # ==================================================
        venta.adjudicar_cliente(cliente)

        messages.success(
            request,
            "Cliente asignado y cuenta corriente creada correctamente."
        )
        return redirect("ventas:lista_unidades_vendidas")

    return render(
        request,
        "ventas/asignar_cliente.html",
        {
            "vehiculo": vehiculo,
            "clientes": clientes
        },
    )


# ==========================================================
# CAMBIO DE ESTADO DEL VEHÍCULO
# ==========================================================
@transaction.atomic
def cambiar_estado_vehiculo(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method != "POST":
        return redirect("vehiculos:lista_vehiculos")

    nuevo_estado = request.POST.get("estado")

    if nuevo_estado == "vendido":

        # 1️⃣ Crear o recuperar la venta
        venta, _ = Venta.objects.get_or_create(
            vehiculo=vehiculo,
            defaults={"estado": "pendiente"}
        )

        # 2️⃣ Marcar vehículo como vendido
        vehiculo.estado = "vendido"
        vehiculo.save(update_fields=["estado"])

        # 3️⃣ Si ya hay cliente, usar el circuito centralizado
        if venta.cliente:
            # 🔑 Esto ahora garantiza:
            # - cuenta corriente
            # - deuda inicial
            # - estado confirmado
            venta.confirmar()

            Gestoria.crear_o_actualizar_desde_venta(
                venta=venta,
                vehiculo=vehiculo,
                cliente=venta.cliente
            )

            messages.success(
                request,
                "La unidad fue vendida y confirmada con cliente."
            )
        else:
            messages.warning(
                request,
                "Unidad marcada como vendida. Asigná el cliente para completar la venta."
            )

        return redirect("ventas:lista_unidades_vendidas")

    # ===============================
    # OTROS ESTADOS
    # ===============================
    vehiculo.estado = nuevo_estado
    vehiculo.save(update_fields=["estado"])

    messages.success(request, "Estado del vehículo actualizado.")
    return redirect("vehiculos:lista_vehiculos")


# ==========================================================
# DETALLE DE VENTA  ✅ (AGREGADO PLAN DE PAGO)
# ==========================================================
def crear_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)

    ficha = getattr(venta.vehiculo, "ficha", None)
    cuenta = _get_venta_cuenta(venta)

    # 🔑 AGREGADO (NO ROMPE NADA)
    plan_pago = getattr(cuenta, "plan_pago", None) if cuenta else None
    cuotas_plan = plan_pago.cuotas.all().order_by("numero") if plan_pago else []

    return render(
        request,
        "ventas/crear_venta.html",
        {
            "venta": venta,
            "vehiculo": venta.vehiculo,
            "ficha": ficha,
            "cliente": venta.cliente,
            "cuenta": cuenta,

            # 👉 NUEVAS VARIABLES
            "plan_pago": plan_pago,
            "cuotas_plan": cuotas_plan,
        },
    )


# ==========================================================
# REVERTIR VENTA
# ==========================================================
@login_required
@transaction.atomic
def revertir_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    vehiculo = venta.vehiculo

    if request.method == "POST":

        planes = PlanPago.objects.filter(
            cuenta__venta=venta
        )

        if CuotaPlan.objects.filter(
            plan__in=planes,
            estado="pagada"
        ).exists():
            messages.error(
                request,
                "No se puede revertir la venta porque existen cuotas pagadas."
            )
            return redirect("ventas:lista_unidades_vendidas")

        CuotaPlan.objects.filter(plan__in=planes).delete()
        planes.delete()

        Gestoria.objects.filter(venta=venta).delete()

        cuenta = _get_venta_cuenta(venta)
        if cuenta:
            cuenta.estado = "cerrada"
            cuenta.save(update_fields=["estado"])

        venta.estado = "revertida"
        venta.cliente = None
        venta.save(update_fields=["estado", "cliente"])

        vehiculo.estado = "stock"
        vehiculo.save(update_fields=["estado"])

        messages.success(
            request,
            "La venta fue revertida y la unidad volvió a stock."
        )

    return redirect("ventas:lista_unidades_vendidas")


# ==========================================================
# ACTUALIZAR PRECIO DE VENTA
# ==========================================================
@login_required
def actualizar_precio_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)

    if request.method == "POST":
        from decimal import Decimal, InvalidOperation
        precio_raw = request.POST.get("precio_venta", "").strip()
        try:
            precio = Decimal(precio_raw.replace(",", "."))
            if precio > 0:
                venta.precio_venta = precio
                venta.save(update_fields=["precio_venta"])
                messages.success(request, "Precio de venta actualizado.")
            else:
                messages.error(request, "El precio debe ser mayor a 0.")
        except (ValueError, InvalidOperation):
            messages.error(request, "Monto inválido.")

    return redirect("ventas:crear_venta", venta_id=venta.id)


# ==========================================================
# COMISIONES POR VENDEDOR (solo admin)
# ==========================================================
def _parse_monto(raw):
    """Devuelve un Decimal > 0 o None si el valor es inválido."""
    from decimal import Decimal, InvalidOperation
    try:
        monto = Decimal((raw or "").strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return monto if monto > 0 else None


@solo_admin
def comisiones_vendedores(request):
    """Listado de cuentas corrientes de comisiones, una por vendedor."""
    from django.contrib.auth.models import User
    from django.db.models import Sum

    cuentas = (
        CuentaVendedor.objects
        .select_related("vendedor")
        .order_by("vendedor__first_name", "vendedor__username")
    )

    total_adeudado = cuentas.aggregate(t=Sum("saldo"))["t"] or 0

    # Vendedores disponibles para cargar una comisión nueva:
    # los que figuran como vendido_por en alguna venta + los que ya tienen cuenta.
    ids_vendedores = set(
        Venta.objects
        .exclude(vendido_por__isnull=True)
        .values_list("vendido_por_id", flat=True)
    )
    ids_vendedores |= set(cuentas.values_list("vendedor_id", flat=True))
    usuarios = (
        User.objects
        .filter(id__in=ids_vendedores)
        .order_by("first_name", "username")
    )

    return render(
        request,
        "ventas/comisiones_vendedores.html",
        {
            "cuentas": cuentas,
            "usuarios": usuarios,
            "total_adeudado": total_adeudado,
        },
    )


@solo_admin
def detalle_comision_vendedor(request, user_id):
    """Detalle de movimientos (comisiones y pagos) de un vendedor."""
    from django.contrib.auth.models import User

    vendedor = get_object_or_404(User, id=user_id)
    cuenta, _ = CuentaVendedor.objects.get_or_create(vendedor=vendedor)

    movimientos = (
        cuenta.movimientos
        .select_related("venta", "venta__vehiculo")
        .all()
    )

    # Ventas de este vendedor, para vincularlas al cargar una comisión.
    ventas_vendedor = (
        Venta.objects
        .filter(vendido_por=vendedor)
        .select_related("vehiculo")
        .order_by("-id")
    )

    return render(
        request,
        "ventas/detalle_comision_vendedor.html",
        {
            "vendedor": vendedor,
            "cuenta": cuenta,
            "movimientos": movimientos,
            "ventas_vendedor": ventas_vendedor,
        },
    )


@solo_admin
def registrar_comision(request):
    """Carga manual de una comisión (haber) a la cuenta de un vendedor."""
    from django.contrib.auth.models import User

    if request.method != "POST":
        return redirect("ventas:comisiones_vendedores")

    vendedor = get_object_or_404(User, id=request.POST.get("vendedor_id"))
    monto = _parse_monto(request.POST.get("monto"))
    if monto is None:
        messages.error(request, "El monto de la comisión debe ser mayor a 0.")
        return redirect("ventas:detalle_comision_vendedor", user_id=vendedor.id)

    venta = None
    venta_id = (request.POST.get("venta_id") or "").strip()
    if venta_id:
        venta = Venta.objects.filter(id=venta_id, vendido_por=vendedor).first()

    cuenta, _ = CuentaVendedor.objects.get_or_create(vendedor=vendedor)
    MovimientoComision.objects.create(
        cuenta=cuenta,
        tipo="comision",
        monto=monto,
        descripcion=(request.POST.get("descripcion") or "").strip(),
        venta=venta,
    )
    messages.success(request, "Comisión registrada.")
    return redirect("ventas:detalle_comision_vendedor", user_id=vendedor.id)


@solo_admin
def registrar_pago_comision(request):
    """Registra un pago al vendedor (debe), que descuenta del saldo."""
    from django.contrib.auth.models import User

    if request.method != "POST":
        return redirect("ventas:comisiones_vendedores")

    vendedor = get_object_or_404(User, id=request.POST.get("vendedor_id"))
    monto = _parse_monto(request.POST.get("monto"))
    if monto is None:
        messages.error(request, "El monto del pago debe ser mayor a 0.")
        return redirect("ventas:detalle_comision_vendedor", user_id=vendedor.id)

    cuenta, _ = CuentaVendedor.objects.get_or_create(vendedor=vendedor)
    MovimientoComision.objects.create(
        cuenta=cuenta,
        tipo="pago",
        monto=monto,
        descripcion=(request.POST.get("descripcion") or "").strip(),
    )
    messages.success(request, "Pago registrado.")
    return redirect("ventas:detalle_comision_vendedor", user_id=vendedor.id)


@solo_admin
def eliminar_movimiento_comision(request, movimiento_id):
    """Elimina un movimiento de comisión y recalcula el saldo."""
    movimiento = get_object_or_404(MovimientoComision, id=movimiento_id)
    user_id = movimiento.cuenta.vendedor_id
    if request.method == "POST":
        movimiento.delete()
        messages.success(request, "Movimiento eliminado.")
    return redirect("ventas:detalle_comision_vendedor", user_id=user_id)