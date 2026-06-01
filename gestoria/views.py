from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q

from .models import Gestoria
from .forms import GestoriaForm


# ==========================================================
# PANTALLA PRINCIPAL GESTORÍA
# ==========================================================
def gestoria_inicio(request):
    return render(request, "gestoria/inicio.html")


# ==========================================================
# GESTORÍAS VIGENTES + BUSCADOR
# ==========================================================
def gestoria_vigentes(request):
    query = request.GET.get("q", "").strip()

    gestorias = (
        Gestoria.objects
        .filter(estado="vigente")
        .select_related("vehiculo", "cliente", "venta")
    )

    if query:
        gestorias = gestorias.filter(
            Q(cliente__nombre_completo__icontains=query) |
            Q(cliente__dni_cuit__icontains=query) |
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(venta__id__icontains=query)
        ).distinct()

    gestorias = gestorias.order_by("-fecha_creacion")

    return render(
        request,
        "gestoria/vigentes.html",
        {
            "gestorias": gestorias,
            "query": query,
        }
    )


# ==========================================================
# GESTORÍAS FINALIZADAS + BUSCADOR
# ==========================================================
def gestoria_finalizadas(request):
    query = request.GET.get("q", "").strip()

    gestorias = (
        Gestoria.objects
        .filter(
            estado="finalizada",
            fecha_finalizacion__isnull=False
        )
        .select_related("vehiculo", "cliente", "venta")
    )

    if query:
        gestorias = gestorias.filter(
            Q(cliente__nombre_completo__icontains=query) |
            Q(cliente__dni_cuit__icontains=query) |
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(venta__id__icontains=query)
        ).distinct()

    gestorias = gestorias.order_by("-fecha_finalizacion")

    return render(
        request,
        "gestoria/finalizadas.html",
        {
            "gestorias": gestorias,
            "query": query,
        }
    )


# ==========================================================
# PDF: LISTADO DE GESTORÍAS (vigentes / finalizadas)
# ==========================================================
def pdf_gestorias(request):
    from datetime import date
    from reportes.pdf_utils import render_pdf_listado

    estado = request.GET.get("estado", "vigente")
    if estado not in ("vigente", "finalizada"):
        estado = "vigente"
    query = request.GET.get("q", "").strip()

    gestorias = (
        Gestoria.objects.filter(estado=estado)
        .select_related("vehiculo", "cliente", "venta")
    )
    if query:
        gestorias = gestorias.filter(
            Q(cliente__nombre_completo__icontains=query) |
            Q(cliente__dni_cuit__icontains=query) |
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(venta__id__icontains=query)
        ).distinct()

    orden = "-fecha_finalizacion" if estado == "finalizada" else "-fecha_creacion"
    gestorias = gestorias.order_by(orden)

    filas = []
    for g in gestorias:
        cli = g.cliente_actual
        fecha_ref = g.fecha_finalizacion or g.fecha_creacion
        filas.append([
            f"{g.vehiculo.marca} {g.vehiculo.modelo}" if g.vehiculo_id else "—",
            (g.vehiculo.dominio or "—") if g.vehiculo_id else "—",
            str(cli) if cli else "Sin cliente",
            (getattr(cli, "telefono", "") or "—") if cli else "—",
            fecha_ref.strftime("%d/%m/%Y") if fecha_ref else "—",
        ])

    titulo = "Gestorías finalizadas" if estado == "finalizada" else "Gestorías vigentes"
    return render_pdf_listado(
        filename=f"gestorias_{estado}.pdf",
        titulo=titulo,
        subtitulo=(f"Búsqueda: «{query}» – " if query else "") + f"{len(filas)} gestoría(s)",
        columnas=["Vehículo", "Dominio", "Cliente", "Teléfono", "Fecha"],
        filas=filas,
        pie=f"Generado el {date.today().strftime('%d/%m/%Y')}",
    )


# ==========================================================
# MARCAR GESTORÍA COMO FINALIZADA
# (SE MANTIENE PARA FLUJOS EXISTENTES)
# ==========================================================
def finalizar_gestoria(request, gestoria_id):
    gestoria = get_object_or_404(Gestoria, id=gestoria_id)

    if request.method == "POST":
        if gestoria.estado != "finalizada":
            gestoria.estado = "finalizada"
            gestoria.fecha_finalizacion = timezone.now()
            gestoria.save(update_fields=["estado", "fecha_finalizacion"])
            messages.success(request, "Gestoría finalizada correctamente")
        else:
            messages.info(request, "La gestoría ya estaba finalizada")
    else:
        messages.warning(request, "Acción inválida")

    return redirect("gestoria:vigentes")


# ==========================================================
# EDITAR / CREAR FICHA DE GESTORÍA
# ==========================================================
def editar_gestoria(request, gestoria_id):
    """
    Pantalla de ficha de gestoría.
    Permite editar documentación, estado y observaciones.
    NO finaliza automáticamente salvo que el estado cambie.
    """

    gestoria = get_object_or_404(Gestoria, id=gestoria_id)

    if request.method == "POST":
        form = GestoriaForm(request.POST, instance=gestoria)
        if form.is_valid():
            g = form.save(commit=False)

            # Fecha de pago de la concesionaria según el check:
            # al marcarlo se sella la fecha (pasa al módulo Pagos Concesionario).
            from datetime import date as _date
            if g.pago_concesionaria_gestionado and not g.pago_concesionaria_fecha:
                g.pago_concesionaria_fecha = _date.today()
            elif not g.pago_concesionaria_gestionado:
                g.pago_concesionaria_fecha = None

            # Finalización controlada desde la ficha
            if g.estado == "finalizada" and not g.fecha_finalizacion:
                g.fecha_finalizacion = timezone.now()

            if g.estado != gestoria.estado:
                messages.info(
                    request,
                    f"Estado de gestoría cambiado a {g.get_estado_display()}"
                )

            g.save()
            messages.success(request, "Gestoría actualizada correctamente")
            return redirect("gestoria:vigentes")
    else:
        form = GestoriaForm(instance=gestoria)

    # Resumen de documentación: leído de la FichaVehicular del vehículo
    ficha = None
    try:
        from vehiculos.models import FichaVehicular
        ficha = FichaVehicular.objects.filter(vehiculo=gestoria.vehiculo).first()
    except Exception:
        ficha = None

    # Recibos de pago del cliente generados desde esta gestoría
    recibos_pago_cliente = []
    if gestoria.venta:
        cuenta = getattr(gestoria.venta, "cuenta_corriente", None)
        if cuenta:
            from cuentas.models import MovimientoCuenta
            movs = (
                MovimientoCuenta.objects
                .filter(
                    cuenta=cuenta, origen="gestoria", tipo="haber",
                    vehiculo=gestoria.vehiculo, pago__isnull=False,
                )
                .select_related("pago")
                .order_by("-fecha")
            )
            recibos_pago_cliente = [m.pago for m in movs]

    return render(
        request,
        "gestoria/gestoria_form.html",
        {
            "gestoria": gestoria,
            "form": form,
            "ficha": ficha,
            "recibos_pago_cliente": recibos_pago_cliente,
        }
    )


# ==========================================================
# HELPER: CREAR O VINCULAR GESTORÍA DESDE VENTA
# (SE MANTIENE, ALINEADO AL MODELO)
# ==========================================================
def crear_o_vincular_gestoria(venta, vehiculo, cliente):
    """
    Se utiliza desde Ventas cuando se asigna un cliente o se confirma una venta.
    Garantiza que la Gestoría exista y esté vinculada al cliente correcto.
    """

    # 🔒 Delegamos la lógica al modelo (fuente única de verdad)
    gestoria = Gestoria.crear_o_actualizar_desde_venta(
        venta=venta,
        vehiculo=vehiculo,
        cliente=cliente
    )

    return gestoria


# ==========================================================
# GENERAR PAGO DEL CLIENTE (+ descuento en cuenta corriente + recibo)
# ==========================================================
def generar_pago_cliente(request, gestoria_id):
    """
    Registra el "Pago cliente" de la gestoría como un Pago en la cuenta
    corriente del cliente (movimiento HABER que descuenta el saldo) y
    redirige al recibo PDF.
    """
    from decimal import Decimal, InvalidOperation
    from cuentas.models import MovimientoCuenta, Pago

    gestoria = get_object_or_404(Gestoria, id=gestoria_id)

    if request.method != "POST":
        return redirect("gestoria:editar_gestoria", gestoria_id=gestoria.id)

    cuenta = None
    if gestoria.venta:
        cuenta = getattr(gestoria.venta, "cuenta_corriente", None)
    if cuenta is None:
        messages.error(
            request,
            "La gestoría no tiene una cuenta corriente vinculada "
            "(se necesita una venta con cuenta corriente)."
        )
        return redirect("gestoria:editar_gestoria", gestoria_id=gestoria.id)

    raw = (request.POST.get("pago_cliente") or "").strip().replace(",", ".")
    try:
        monto = Decimal(raw)
    except (InvalidOperation, ValueError):
        messages.error(request, "Monto de pago cliente inválido.")
        return redirect("gestoria:editar_gestoria", gestoria_id=gestoria.id)

    if monto <= 0:
        messages.error(request, "El pago del cliente debe ser mayor a 0.")
        return redirect("gestoria:editar_gestoria", gestoria_id=gestoria.id)

    forma = request.POST.get("forma_pago_cliente") or "efectivo"
    if forma not in dict(Pago.FORMAS_PAGO):
        forma = "efectivo"

    saldo_anterior = cuenta.saldo

    pago = Pago.objects.create(
        cuenta=cuenta,
        forma_pago=forma,
        monto_total=monto,
        observaciones=f"Pago cliente – Gestoría {gestoria.vehiculo}",
    )
    MovimientoCuenta.objects.create(
        cuenta=cuenta,
        descripcion=f"Pago cliente gestoría – {gestoria.vehiculo}",
        tipo="haber",
        monto=monto,
        origen="gestoria",
        vehiculo=gestoria.vehiculo,
        pago=pago,
    )
    cuenta.recalcular_saldo()

    pago.saldo_anterior = saldo_anterior
    pago.saldo_posterior = cuenta.saldo
    pago.save(update_fields=["saldo_anterior", "saldo_posterior"])

    # Guardar el monto en la gestoría
    if gestoria.pago_cliente != monto:
        gestoria.pago_cliente = monto
        gestoria.save(update_fields=["pago_cliente"])

    messages.success(
        request,
        f"Pago del cliente de ${monto} registrado y descontado de la "
        f"cuenta corriente. Recibo {pago.numero_recibo} generado — "
        f"usá el botón «Imprimir recibo» para descargarlo."
    )
    return redirect("gestoria:editar_gestoria", gestoria_id=gestoria.id)


# ==========================================================
# MÓDULO: PAGOS CONCESIONARIO
# Listado de gestorías cuyo "Pago concesionaria" fue gestionado.
# ==========================================================
def pagos_concesionario(request):
    from django.db.models import Sum

    query = request.GET.get("q", "").strip()
    gestorias = (
        Gestoria.objects.filter(pago_concesionaria_gestionado=True)
        .select_related("vehiculo", "cliente", "venta")
    )
    if query:
        gestorias = gestorias.filter(
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(cliente__nombre_completo__icontains=query)
        ).distinct()

    gestorias = gestorias.order_by("-pago_concesionaria_fecha", "-fecha_creacion")
    total = gestorias.aggregate(t=Sum("pago_concesionaria"))["t"] or 0

    return render(
        request,
        "gestoria/pagos_concesionario.html",
        {
            "gestorias": gestorias,
            "query": query,
            "total": total,
        }
    )