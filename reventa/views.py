from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.db import transaction

from .models import Reventa
from vehiculos.models import Vehiculo


# ==========================================================
# LISTA DE REVENTAS
# ==========================================================
@login_required
def lista_reventas(request):
    q = request.GET.get("q", "")

    reventas = Reventa.objects.filter(
        estado__in=["pendiente", "confirmada"],
    ).select_related("vehiculo", "cuenta")

    if q:
        reventas = reventas.filter(
            Q(vehiculo__marca__icontains=q)
            | Q(vehiculo__modelo__icontains=q)
            | Q(vehiculo__dominio__icontains=q)
            | Q(agencia__icontains=q)
        )

    pendientes = reventas.filter(estado="pendiente")
    confirmadas = reventas.filter(estado="confirmada")

    return render(request, "reventa/lista.html", {
        "pendientes": pendientes,
        "confirmadas": confirmadas,
        "query": q,
    })


# ==========================================================
# ASIGNAR AGENCIA / COMPRADOR
# ==========================================================
@login_required
def asignar_reventa(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    reventa = get_object_or_404(Reventa, vehiculo=vehiculo)

    if reventa.agencia and reventa.estado == "confirmada":
        messages.info(request, "Esta reventa ya tiene agencia asignada y esta confirmada.")
        return redirect("reventa:lista")

    if request.method == "POST":
        agencia = request.POST.get("agencia", "").strip()
        contacto = request.POST.get("contacto", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        precio = request.POST.get("precio_reventa", "").replace(",", ".")
        comision = request.POST.get("comision", "0").replace(",", ".")
        observaciones = request.POST.get("observaciones", "").strip()

        if not agencia:
            messages.error(request, "La agencia/comprador es obligatoria.")
            return redirect("reventa:asignar", vehiculo_id=vehiculo.id)

        reventa.agencia = agencia
        reventa.contacto = contacto
        reventa.telefono = telefono
        reventa.observaciones = observaciones

        try:
            from decimal import Decimal
            if precio:
                reventa.precio_reventa = Decimal(precio)
            if comision:
                reventa.comision = Decimal(comision)
        except Exception:
            pass

        reventa.confirmar()

        messages.success(
            request,
            f"Reventa asignada a \"{agencia}\" y confirmada.",
        )
        return redirect("reventa:lista")

    return render(request, "reventa/asignar.html", {
        "vehiculo": vehiculo,
        "reventa": reventa,
    })


# ==========================================================
# REVERTIR REVENTA (VOLVER A STOCK)
# ==========================================================
# ==========================================================
# EDITAR REVENTA
# ==========================================================
@login_required
def editar_reventa(request, reventa_id):
    reventa = get_object_or_404(Reventa, id=reventa_id)

    if request.method == "POST":
        reventa.agencia = request.POST.get("agencia", "").strip()
        reventa.contacto = request.POST.get("contacto", "").strip()
        reventa.telefono = request.POST.get("telefono", "").strip()
        reventa.observaciones = request.POST.get("observaciones", "").strip()

        precio = request.POST.get("precio_reventa", "").replace(",", ".")
        comision = request.POST.get("comision", "0").replace(",", ".")

        try:
            from decimal import Decimal
            if precio:
                reventa.precio_reventa = Decimal(precio)
            if comision:
                reventa.comision = Decimal(comision)
        except Exception:
            pass

        reventa.save()
        messages.success(request, "Reventa actualizada.")
        return redirect("reventa:lista")

    return render(request, "reventa/editar.html", {
        "reventa": reventa,
        "vehiculo": reventa.vehiculo,
    })


@login_required
@transaction.atomic
def revertir_reventa(request, reventa_id):
    reventa = get_object_or_404(Reventa, id=reventa_id)

    if request.method == "POST":
        vehiculo = reventa.vehiculo
        reventa.revertir()

        messages.success(
            request,
            f"Reventa revertida. {vehiculo} volvio a stock.",
        )

    return redirect("reventa:lista")


# ==========================================================
# ELIMINAR REVENTA
# ==========================================================
@login_required
def eliminar_reventa(request, reventa_id):
    reventa = get_object_or_404(Reventa, id=reventa_id)

    if request.method == "POST":
        vehiculo = reventa.vehiculo
        if vehiculo and vehiculo.estado == "reventa":
            vehiculo.estado = "stock"
            vehiculo.save(update_fields=["estado"])
        reventa.delete()
        messages.success(request, "Reventa eliminada.")

    return redirect("reventa:lista")


# ==========================================================
# CUENTAS DE REVENDEDORES
# ==========================================================
@login_required
def lista_cuentas_revendedores(request):
    q = request.GET.get("q", "")
    from .models import CuentaRevendedor
    cuentas = CuentaRevendedor.objects.filter(activa=True)
    if q:
        cuentas = cuentas.filter(Q(nombre__icontains=q))

    from django.db.models import Sum
    total_deuda = cuentas.filter(saldo__gt=0).aggregate(t=Sum("saldo"))["t"] or 0

    return render(request, "reventa/cuentas_lista.html", {
        "cuentas": cuentas,
        "query": q,
        "total_deuda": total_deuda,
    })


@login_required
def crear_cuenta_revendedor(request):
    from .models import CuentaRevendedor
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        contacto = request.POST.get("contacto", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        direccion = request.POST.get("direccion", "").strip()

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return redirect("reventa:crear_cuenta")

        CuentaRevendedor.objects.create(
            nombre=nombre,
            contacto=contacto,
            telefono=telefono,
            direccion=direccion,
        )
        messages.success(request, f"Cuenta \"{nombre}\" creada.")
        return redirect("reventa:cuentas")

    return render(request, "reventa/cuenta_form.html", {
        "titulo": "Nueva Cuenta de Revendedor",
    })


@login_required
def detalle_cuenta_revendedor(request, pk):
    from .models import CuentaRevendedor
    cuenta = get_object_or_404(CuentaRevendedor, pk=pk)
    movimientos = cuenta.movimientos.all()

    return render(request, "reventa/cuenta_detalle.html", {
        "cuenta": cuenta,
        "movimientos": movimientos,
    })


@login_required
def agregar_movimiento_revendedor(request, pk):
    from .models import CuentaRevendedor, MovimientoRevendedor
    cuenta = get_object_or_404(CuentaRevendedor, pk=pk)

    if request.method == "POST":
        tipo = request.POST.get("tipo", "debe")
        monto_raw = request.POST.get("monto", "0").replace(",", ".")
        descripcion = request.POST.get("descripcion", "").strip()

        if not descripcion:
            messages.error(request, "La descripcion es obligatoria.")
            return redirect("reventa:detalle_cuenta", pk=cuenta.pk)

        try:
            from decimal import Decimal
            monto = Decimal(monto_raw)
        except Exception:
            messages.error(request, "Monto invalido.")
            return redirect("reventa:detalle_cuenta", pk=cuenta.pk)

        MovimientoRevendedor.objects.create(
            cuenta=cuenta,
            tipo=tipo,
            monto=monto,
            descripcion=descripcion,
        )
        messages.success(request, "Movimiento registrado.")

    return redirect("reventa:detalle_cuenta", pk=cuenta.pk)


@login_required
def eliminar_movimiento_revendedor(request, pk):
    from .models import MovimientoRevendedor
    movimiento = get_object_or_404(MovimientoRevendedor, pk=pk)
    cuenta_pk = movimiento.cuenta.pk

    if request.method == "POST":
        movimiento.delete()
        messages.success(request, "Movimiento eliminado.")

    return redirect("reventa:detalle_cuenta", pk=cuenta_pk)
