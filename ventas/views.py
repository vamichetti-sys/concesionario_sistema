from django.shortcuts import render, redirect, get_object_or_404
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
from .models import Venta


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
        cliente = get_object_or_404(Cliente, id=request.POST.get("cliente"))

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