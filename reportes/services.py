"""
Helpers de ganancia reutilizables (mismo cálculo que Control de Stock /
Reportes): ganancia = precio_venta − precio_compra − gastos del vehículo.
"""
from decimal import Decimal
from django.db.models import Sum

GC_FIELDS = [
    "gc_service", "gc_mecanica", "gc_chapa_pintura", "gc_tapizado",
    "gc_neumaticos", "gc_vidrios", "gc_cerrajeria", "gc_lavado",
    "gc_gnc", "gc_grabado_autopartes", "gc_vtv", "gc_verificacion",
    "gc_patentes", "gc_otros",
]


def ganancia_venta(venta):
    """Ganancia neta de una venta (precio − compra − gastos del vehículo)."""
    from compraventa.models import CompraVentaOperacion
    from vehiculos.models import FichaVehicular, GastoConcesionario

    if not venta.vehiculo_id:
        return Decimal("0")

    op = CompraVentaOperacion.objects.filter(vehiculo_id=venta.vehiculo_id).first()
    precio_compra = (op.precio_compra if op and op.precio_compra else Decimal("0"))

    gastos = Decimal("0")
    ficha = FichaVehicular.objects.filter(vehiculo_id=venta.vehiculo_id).first()
    if ficha:
        for f in GC_FIELDS:
            gastos += getattr(ficha, f, None) or Decimal("0")
    gastos += (
        GastoConcesionario.objects.filter(vehiculo_id=venta.vehiculo_id)
        .aggregate(t=Sum("monto"))["t"] or Decimal("0")
    )

    return (venta.precio_venta or Decimal("0")) - precio_compra - gastos


def ganancia_ventas_mes(mes, anio):
    """
    Ganancia de las ventas confirmadas en el mes/año (Control de Stock).
    Devuelve (total, [{venta, ganancia}, ...]).
    """
    from ventas.models import Venta

    total = Decimal("0")
    detalles = []
    qs = (
        Venta.objects.filter(estado="confirmada", fecha_venta__year=anio, fecha_venta__month=mes)
        .select_related("vehiculo", "cliente")
        .order_by("-fecha_venta")
    )
    for v in qs:
        g = ganancia_venta(v)
        total += g
        detalles.append({"venta": v, "ganancia": g})
    return total, detalles
