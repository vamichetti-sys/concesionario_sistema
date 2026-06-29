from decimal import Decimal
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.db.models import Q, Sum, Case, When, IntegerField, Value
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Vehiculo,
    FichaVehicular,
    FichaTecnica,
    PagoGastoIngreso,
    ConfiguracionGastosIngreso,
    GastoConcesionario,
    PagoGastoConcesionario,
    Mantenimiento,
)

from .forms import VehiculoBasicoForm, VehiculoForm, FichaVehicularForm, FichaTecnicaForm

# ===============================
# REPORTLAB – PDF (SIN DEPENDENCIAS NATIVAS)
# ===============================
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


# ==========================================================
# GASTOS DE CONCESIONARIO — conceptos fijos + pago de gastos
# ==========================================================
GASTOS_CONC_CAMPOS = [
    ("gc_service", "Service"),
    ("gc_mecanica", "Mecanica"),
    ("gc_chapa_pintura", "Chapa y pintura"),
    ("gc_tapizado", "Tapizado"),
    ("gc_neumaticos", "Neumaticos"),
    ("gc_vidrios", "Vidrios"),
    ("gc_cerrajeria", "Cerrajeria"),
    ("gc_lavado", "Lavado / Pulido"),
    ("gc_gnc", "GNC"),
    ("gc_grabado_autopartes", "Grabado autopartes"),
    ("gc_vtv", "VTV"),
    ("gc_verificacion", "Verificacion policial"),
    ("gc_patentes", "Patentes"),
    ("gc_otros", "Otros"),
]

# Etiquetas para resolver el nombre de un concepto de gasto de concesionario
GASTOS_CONC_LABELS = dict(GASTOS_CONC_CAMPOS)


def construir_gastos_conc_pago(vehiculo, ficha, gastos_extras):
    """Data para 'Pago de gastos de concesionario'.

    Para cada gasto fijo (gc_*) con monto > 0 y para cada gasto adicional,
    calcula total pagado y saldo (mismo patrón que gastos de ingreso). Devuelve
    también el historial de pagos del vehículo.
    """
    pagos_qs = PagoGastoConcesionario.objects.filter(vehiculo=vehiculo)

    def _pagado(key):
        return pagos_qs.filter(concepto=key).aggregate(t=Sum("monto"))["t"] or Decimal("0")

    items = []

    for campo, label in GASTOS_CONC_CAMPOS:
        monto = Decimal(getattr(ficha, campo, None) or 0)
        if monto <= 0:
            continue
        pagado = Decimal(_pagado(campo))
        saldo = monto - pagado
        items.append({
            "key": campo,
            "concepto": label,
            "monto": monto,
            "total_pagado": pagado,
            "saldo": saldo,
            "esta_pagado": saldo <= 0,
        })

    for extra in gastos_extras:
        monto = Decimal(extra.monto or 0)
        if monto <= 0:
            continue
        key = f"extra:{extra.pk}"
        pagado = Decimal(_pagado(key))
        saldo = monto - pagado
        items.append({
            "key": key,
            "concepto": extra.concepto,
            "monto": monto,
            "total_pagado": pagado,
            "saldo": saldo,
            "esta_pagado": saldo <= 0,
        })

    total_pendiente = sum((i["saldo"] for i in items if i["saldo"] > 0), Decimal("0"))
    total_pagado = sum((i["total_pagado"] for i in items), Decimal("0"))

    # Historial con etiqueta legible del concepto
    extras_labels = {f"extra:{e.pk}": e.concepto for e in gastos_extras}
    pagos = list(pagos_qs.order_by("-fecha_pago", "-creado"))
    for p in pagos:
        p.concepto_label = (
            GASTOS_CONC_LABELS.get(p.concepto)
            or extras_labels.get(p.concepto)
            or p.concepto
        )

    return {
        "gastos_conc_pago": items,
        "total_pendiente_conc": total_pendiente,
        "total_pagado_conc": total_pagado,
        "pagos_conc": pagos,
    }


# ==========================================================
# ACCESO ÚNICO A CONFIGURACIÓN GLOBAL DE GASTOS (ÚNICO VÁLIDO)
# ==========================================================
def get_configuracion_gastos():
    config, _ = ConfiguracionGastosIngreso.objects.get_or_create(pk=1)
    return config


def _clientes_para_titular():
    """Clientes activos para el autocompletado del titular en la ficha."""
    from clientes.models import Cliente
    qs = (
        Cliente.objects.filter(activo=True)
        .order_by("nombre_completo")
        .values("id", "nombre_completo", "dni_cuit", "telefono", "email", "direccion")
    )
    return [
        {
            "id": c["id"],
            "nombre": c["nombre_completo"] or "",
            "dni": c["dni_cuit"] or "",
            "telefono": c["telefono"] or "",
            "email": c["email"] or "",
            "domicilio": c["direccion"] or "",
        }
        for c in qs
    ]


# ==========================================================
# LISTA DE VEHÍCULOS CON FILTROS Y DÍAS EN STOCK
# ==========================================================
def lista_vehiculos(request):
    query = request.GET.get("q", "")
    # Por defecto se muestra el stock (los disponibles). Para ver el resto
    # el usuario tiene que cambiar de tab.
    estado_filtro = request.GET.get("estado", "stock")

    vehiculos = (
        Vehiculo.objects
        .all()
        .select_related('ficha', 'ficha_reporte')
        .annotate(
            estado_orden=Case(
                When(estado="a_ingresar", then=Value(0)),
                When(estado="stock", then=Value(1)),
                When(estado="temporal", then=Value(2)),
                When(estado="reventa", then=Value(3)),
                When(estado="vendido", then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
        .order_by("estado_orden", "marca", "modelo", "-id")
    )

    # Filtro por búsqueda
    if query:
        vehiculos = vehiculos.filter(
            Q(marca__icontains=query)
            | Q(modelo__icontains=query)
            | Q(dominio__icontains=query)
        )

    # Filtro por estado:
    #   "todos" → no filtra (incluye todos los estados)
    #   <estado puntual> → filtra por ese estado exacto
    if estado_filtro and estado_filtro != "todos":
        vehiculos = vehiculos.filter(estado=estado_filtro)

    # Calcular días en stock para cada vehículo
    hoy = date.today()
    vehiculos_con_dias = []
    
    for v in vehiculos:
        dias_en_stock = None
        
        # Buscar fecha_compra en FichaReporteInterno
        if hasattr(v, 'ficha_reporte') and v.ficha_reporte and v.ficha_reporte.fecha_compra:
            dias_en_stock = (hoy - v.ficha_reporte.fecha_compra).days
        
        vehiculos_con_dias.append({
            'vehiculo': v,
            'dias_en_stock': dias_en_stock
        })

    # Contadores para los filtros
    total_a_ingresar = Vehiculo.objects.filter(estado='a_ingresar').count()
    total_stock = Vehiculo.objects.filter(estado='stock').count()
    total_temporal = Vehiculo.objects.filter(estado='temporal').count()
    total_vendido = Vehiculo.objects.filter(estado='vendido').count()
    total_reventa = Vehiculo.objects.filter(estado='reventa').count()

    from django.contrib.auth.models import User
    usuarios_vendedores = User.objects.filter(is_active=True).order_by("username")

    return render(
        request,
        "vehiculos/lista_vehiculos.html",
        {
            "vehiculos_con_dias": vehiculos_con_dias,
            "query": query,
            "estado_filtro": estado_filtro,
            "total_a_ingresar": total_a_ingresar,
            "total_stock": total_stock,
            "total_temporal": total_temporal,
            "total_vendido": total_vendido,
            "total_reventa": total_reventa,
            "usuarios_vendedores": usuarios_vendedores,
        },
    )


def lista_vehiculos_vendidos(request):
    vehiculos = Vehiculo.objects.filter(estado="vendido").order_by("-id")

    return render(
        request,
        "vehiculos/lista_vehiculos_vendidos.html",
        {"vehiculos": vehiculos},
    )


def agregar_vehiculo(request):
    if request.method == "POST":
        form = VehiculoBasicoForm(request.POST)

        if form.is_valid():
            vehiculo = form.save()

            # 👉 aplicar configuración global SOLO al crear ficha
            config = get_configuracion_gastos()

            FichaVehicular.objects.get_or_create(
                vehiculo=vehiculo,
                defaults={
                    "gasto_f08": config.gasto_f08,
                    "gasto_informes": config.gasto_informes,
                    "gasto_patentes": config.gasto_patentes,
                    "gasto_infracciones": config.gasto_infracciones,
                    "gasto_verificacion": config.gasto_verificacion,
                    "gasto_autopartes": config.gasto_autopartes,
                    "gasto_vtv": config.gasto_vtv,
                    "gasto_r541": config.gasto_r541,
                    "gasto_firmas": config.gasto_firmas,
                }
            )

            messages.success(request, "Vehículo agregado correctamente.")
            return redirect("vehiculos:lista_vehiculos")

        # ❌ formulario inválido
        messages.error(
            request,
            "No se pudo guardar el vehículo. Revisá los datos ingresados."
        )

    else:
        form = VehiculoBasicoForm()

    return render(
        request,
        "vehiculos/agregar_vehiculo.html",
        {"form": form},
    )


@login_required
@transaction.atomic
def reingresar_a_stock(request, vehiculo_id):
    """
    Reingresa un vehículo vendido al stock para volver a venderlo.
    - Archiva la venta anterior eliminándola del modelo (queda snapshot
      completo en auditoría con accion=eliminar).
    - Desvincula la cuenta corriente vinculada (no se borra, queda como
      historial cerrado).
    - Desvincula facturas (idem).
    - Borra gestoría asociada.
    - Permite actualizar el precio de venta en el mismo paso.
    """
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method != "POST":
        return redirect("vehiculos:lista_vehiculos")

    nuevo_precio_raw = (request.POST.get("nuevo_precio") or "").strip().replace(",", ".")
    if nuevo_precio_raw:
        try:
            vehiculo.precio = Decimal(nuevo_precio_raw)
        except Exception:
            messages.warning(request, "El precio ingresado es inválido — el reingreso se hizo igual.")

    vehiculo.estado = "stock"
    vehiculo.save(update_fields=["estado", "precio"])

    if hasattr(vehiculo, "venta"):
        try:
            venta = vehiculo.venta
            from cuentas.models import CuentaCorriente
            CuentaCorriente.objects.filter(venta=venta).update(
                venta=None, estado="cerrada"
            )
            from facturacion.models import FacturaRegistrada
            FacturaRegistrada.objects.filter(venta=venta).update(venta=None)
            venta.delete()
        except Exception:
            pass

    try:
        from gestoria.models import Gestoria
        Gestoria.objects.filter(vehiculo=vehiculo).delete()
    except Exception:
        pass

    messages.success(
        request,
        f"Vehículo {vehiculo} reingresado a stock. "
        "La venta anterior quedó registrada en Auditoría (Registros eliminados)."
    )
    return redirect("vehiculos:lista_vehiculos")


@transaction.atomic
def cambiar_estado_vehiculo(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    # Estados que pueden setearse desde el dropdown.
    ESTADOS_VALIDOS = {"a_ingresar", "stock", "temporal", "vendido", "reventa"}

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")

        # ===============================
        # VALIDACIÓN
        # ===============================
        if nuevo_estado not in ESTADOS_VALIDOS:
            messages.error(request, "Estado inválido.")
            return redirect("vehiculos:lista_vehiculos")

        if nuevo_estado == vehiculo.estado:
            return redirect("vehiculos:lista_vehiculos")

        # Bloqueo de seguridad: si el auto está VENDIDO y se intenta
        # cambiar a stock/temporal/reventa desde acá, redirigimos al
        # flujo correcto (Reingresar a stock) que pide confirmación
        # explícita antes de borrar la venta.
        if vehiculo.estado == "vendido" and hasattr(vehiculo, "venta"):
            if nuevo_estado != "vendido":
                messages.error(
                    request,
                    "Para sacar este auto del estado VENDIDO usá el botón "
                    "'Reingresar' (pide confirmación porque borra la venta y "
                    "cierra la cuenta corriente)."
                )
                return redirect("vehiculos:lista_vehiculos")

        # ===============================
        # MARCAR COMO VENDIDO
        # ===============================
        if nuevo_estado == "vendido":
            from ventas.models import Venta
            from gestoria.models import Gestoria
            from reportes.models import FichaReporteInterno

            # ===============================
            # PRECIO DE VENTA (preguntado en el modal)
            # Si no llega, usamos el precio de lista del vehículo.
            # ===============================
            precio_raw = (request.POST.get("precio_venta") or "").strip().replace("$", "").replace(" ", "")
            if "," in precio_raw:
                precio_raw = precio_raw.replace(".", "").replace(",", ".")
            try:
                precio_venta = Decimal(precio_raw) if precio_raw else vehiculo.precio
            except Exception:
                precio_venta = vehiculo.precio

            # Fecha de venta (opcional en el modal). Si no llega, usamos hoy.
            fecha_raw = (request.POST.get("fecha_venta") or "").strip()
            try:
                fecha_venta = date.fromisoformat(fecha_raw) if fecha_raw else date.today()
            except ValueError:
                fecha_venta = date.today()

            # ¿Quién lo vendió? (opcional, llega del modal)
            vendido_por = None
            vendedor_id = (request.POST.get("vendido_por") or "").strip()
            if vendedor_id:
                from django.contrib.auth.models import User
                vendido_por = User.objects.filter(pk=vendedor_id).first()

            venta, creada = Venta.objects.get_or_create(
                vehiculo=vehiculo,
                defaults={
                    "estado": "confirmada",
                    "precio_venta": precio_venta,
                    "vendido_por": vendido_por,
                }
            )

            # Aunque la venta ya existiera, registramos el precio acordado y la confirmamos.
            campos_venta = []
            if not creada and venta.estado != "confirmada":
                venta.estado = "confirmada"
                campos_venta.append("estado")
            if venta.precio_venta != precio_venta:
                venta.precio_venta = precio_venta
                campos_venta.append("precio_venta")
            if vendido_por is not None and venta.vendido_por_id != vendido_por.id:
                venta.vendido_por = vendido_por
                campos_venta.append("vendido_por")
            if campos_venta:
                venta.save(update_fields=campos_venta)

            vehiculo.estado = "vendido"
            vehiculo.save(update_fields=["estado"])

            # ===============================
            # VINCULAR CON REPORTE INTERNO
            # El precio de venta queda registrado automáticamente en la
            # ficha interna del vehículo (para el cálculo de ganancia).
            # ===============================
            ficha, _ = FichaReporteInterno.objects.get_or_create(vehiculo=vehiculo)
            ficha.precio_venta = precio_venta
            ficha.fecha_venta = fecha_venta
            if venta.cliente and not ficha.comprador:
                ficha.comprador = str(venta.cliente)
            # Si todavía no se cargó el precio de compra, lo tomamos de compra-venta.
            if ficha.precio_compra is None:
                operacion = getattr(vehiculo, "operacion_compra", None)
                if operacion and operacion.precio_compra:
                    ficha.precio_compra = operacion.precio_compra
                    if not ficha.fecha_compra:
                        ficha.fecha_compra = operacion.fecha_compra
            ficha.save()

            if venta.cliente:
                Gestoria.objects.get_or_create(
                    venta=venta,
                    defaults={
                        "vehiculo": vehiculo,
                        "cliente": venta.cliente,
                        "estado": "vigente",
                    }
                )
                messages.success(
                    request,
                    "Unidad marcada como vendida y enviada a Ventas y Gestoría."
                )
            else:
                messages.warning(
                    request,
                    "Unidad marcada como vendida. Asigná el cliente para completar la operación."
                )

            return redirect("ventas:lista_unidades_vendidas")

        # ===============================
        # MARCAR COMO REVENTA
        # ===============================
        if nuevo_estado == "reventa":
            from reventa.models import Reventa

            # Si ya tiene una reventa revertida, la eliminamos primero
            Reventa.objects.filter(vehiculo=vehiculo, estado="revertida").delete()

            reventa, creada = Reventa.objects.get_or_create(
                vehiculo=vehiculo,
                defaults={
                    "estado": "pendiente",
                    "precio_reventa": vehiculo.precio,
                }
            )

            if not creada and reventa.estado != "pendiente":
                reventa.estado = "pendiente"
                reventa.precio_reventa = vehiculo.precio
                reventa.save(update_fields=["estado", "precio_reventa"])

            vehiculo.estado = "reventa"
            vehiculo.save(update_fields=["estado"])

            messages.warning(
                request,
                "Unidad enviada a reventa. Asigna la agencia/comprador para completar."
            )
            return redirect("reventa:lista")

        # ===============================
        # CAMBIO SEGURO ENTRE A INGRESAR / STOCK / TEMPORAL
        # (no toca venta/gestoría/cuenta corriente)
        # ===============================
        if nuevo_estado in ("a_ingresar", "stock", "temporal"):
            vehiculo.estado = nuevo_estado
            vehiculo.save(update_fields=["estado"])
            messages.success(
                request,
                f"Estado actualizado a {dict(Vehiculo.ESTADOS).get(nuevo_estado, nuevo_estado)}."
            )

    return redirect("vehiculos:lista_vehiculos")


# ==========================================================
# MODAL FICHA VEHICULAR (AJAX) – DEFINITIVA
# ==========================================================
def ficha_vehicular_ajax(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)
    ficha_tec, _ = FichaTecnica.objects.get_or_create(vehiculo=vehiculo)

    vehiculo_form = VehiculoForm(instance=vehiculo)
    ficha_form = FichaVehicularForm(instance=ficha)
    ficha_tecnica_form = FichaTecnicaForm(instance=ficha_tec)

    CONCEPTOS = {
        "f08": "Formulario 08",
        "informes": "Informes",
        "patentes": "Patentes",
        "infracciones": "Infracciones",
        "verificacion": "Verificación",
        "autopartes": "Autopartes",
        "vtv": "VTV",
        "r541": "R541",
        "firmas": "Firmas",
    }

    mapa_gastos = {
        "f08": ficha.gasto_f08,
        "informes": ficha.gasto_informes,
        "patentes": ficha.gasto_patentes,
        "infracciones": ficha.gasto_infracciones,
        "verificacion": ficha.gasto_verificacion,
        "autopartes": ficha.gasto_autopartes,
        "vtv": ficha.gasto_vtv,
        "r541": ficha.gasto_r541,
        "firmas": ficha.gasto_firmas,
    }

    gastos_ingreso = []

    for key, monto in mapa_gastos.items():
        if monto is None:
            continue

        monto = Decimal(monto)
        if monto <= 0:
            continue

        total_pagado = (
            PagoGastoIngreso.objects.filter(
                vehiculo=vehiculo,
                concepto=key,
                situacion__in=["prov_directo", "cli_directo", "cli_adelanto", "prov_reintegro"],
            ).aggregate(total=Sum("monto"))["total"]
            or Decimal("0")
        )

        saldo = monto - Decimal(total_pagado)

        # 🔴 FILTRO CLAVE: SI EL SALDO ES 0, NO SE MUESTRA
        if saldo <= 0:
            continue

        gastos_ingreso.append({
            "key": key,
            "concepto": CONCEPTOS[key],
            "monto": monto,
            "total_pagado": total_pagado,
            "saldo": saldo,
            "ente_sugerido": ENTE_SUGERIDO.get(key, ""),
        })

    total_pendiente = sum(
        (g["saldo"] for g in gastos_ingreso if g["saldo"] > 0),
        Decimal("0")
    )

    # Gastos concesionario
    GASTOS_CONC_CAMPOS = [
        ("gc_service", "Service"),
        ("gc_mecanica", "Mecanica"),
        ("gc_chapa_pintura", "Chapa y pintura"),
        ("gc_tapizado", "Tapizado"),
        ("gc_neumaticos", "Neumaticos"),
        ("gc_vidrios", "Vidrios"),
        ("gc_cerrajeria", "Cerrajeria"),
        ("gc_lavado", "Lavado / Pulido"),
        ("gc_gnc", "GNC"),
        ("gc_grabado_autopartes", "Grabado autopartes"),
        ("gc_vtv", "VTV"),
        ("gc_verificacion", "Verificacion policial"),
        ("gc_patentes", "Patentes"),
        ("gc_otros", "Otros"),
    ]
    gastos_conc_items = []
    total_gastos_conc = Decimal("0")
    for campo, label in GASTOS_CONC_CAMPOS:
        monto = getattr(ficha, campo, None) or Decimal("0")
        gastos_conc_items.append({"campo": campo, "label": label, "monto": monto})
        total_gastos_conc += Decimal(monto)

    gastos_extras = GastoConcesionario.objects.filter(vehiculo=vehiculo)
    total_extras = gastos_extras.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    total_gastos_conc += total_extras

    # Pago de gastos de concesionario (mismo patrón que gastos de ingreso)
    ctx_pago_conc = construir_gastos_conc_pago(vehiculo, ficha, gastos_extras)

    html = render_to_string(
        "vehiculos/modal_ficha_vehicular.html",
        {
            "vehiculo": vehiculo,
            "ficha": ficha,
            "vehiculo_form": vehiculo_form,
            "ficha_form": ficha_form,
            "gastos_ingreso": gastos_ingreso,
            "total_pendiente": total_pendiente,
            "gastos_conc_items": gastos_conc_items,
            "gastos_extras": gastos_extras,
            "total_gastos_conc": total_gastos_conc,
            "ficha_tecnica_form": ficha_tecnica_form,
            "mantenimientos": vehiculo.mantenimientos.all(),
            "clientes_titular": _clientes_para_titular(),
            "tiene_proveedor": ficha.vendedor_id is not None,
            **ctx_pago_conc,
        },
        request=request,
    )

    return JsonResponse({"html": html})


# ==========================================================
# GUARDAR FICHA VEHICULAR (FINAL – LIMPIO Y CORRECTO)
# ==========================================================
@transaction.atomic
def guardar_ficha_vehicular(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)
    ficha_tec, _ = FichaTecnica.objects.get_or_create(vehiculo=vehiculo)

    if request.method == "POST":

        vehiculo_form = VehiculoForm(request.POST, instance=vehiculo)

        # 🔒 ANTI-BORRADO: la ficha es multi-pestaña. Cada pestaña manda solo
        # SUS campos. Si construimos el form con los 63 campos, los campos de
        # las otras pestañas (que no vienen en el POST) se guardarían vacíos y
        # se pierde la información. Por eso armamos el form SOLO con los campos
        # que realmente vinieron en el POST.
        campos_enviados = [
            campo for campo in FichaVehicularForm.Meta.fields
            if campo in request.POST or campo in request.FILES
        ]

        class FichaParcialForm(FichaVehicularForm):
            class Meta(FichaVehicularForm.Meta):
                fields = campos_enviados

        ficha_form = FichaParcialForm(request.POST, request.FILES, instance=ficha)

        # 🔒 ANTI-BORRADO ficha técnica: igual que la ficha vehicular, solo
        # tocamos los campos técnicos que realmente vinieron en el POST. Si la
        # pestaña que se guardó NO incluye campos técnicos (ej. "Datos del
        # Vehículo"), no construimos el form → no se pisa la ficha técnica.
        tecnica_campos_enviados = [
            c for c in FichaTecnicaForm.base_fields.keys()
            if c in request.POST or c in request.FILES
        ]
        if tecnica_campos_enviados:
            class FichaTecnicaParcialForm(FichaTecnicaForm):
                class Meta(FichaTecnicaForm.Meta):
                    fields = tecnica_campos_enviados
                    exclude = None
            ficha_tecnica_form = FichaTecnicaParcialForm(request.POST, instance=ficha_tec)
        else:
            ficha_tecnica_form = None

        if vehiculo_form.is_valid() and ficha_form.is_valid():

            # ===============================
            # GUARDAR VEHÍCULO
            # ===============================
            vehiculo_guardado = vehiculo_form.save(commit=False)

            if vehiculo.estado == "vendido":
                vehiculo_guardado.estado = "vendido"

            vehiculo_guardado.save()

            # ===============================
            # GUARDAR FICHA
            # ===============================
            # Preservar gastos de ingreso y concesionario antes de que el form los sobreescriba
            gastos_preservar = {}
            campos_a_preservar = [
                "gasto_f08", "gasto_informes", "gasto_patentes", "gasto_infracciones",
                "gasto_verificacion", "gasto_autopartes", "gasto_vtv", "gasto_r541", "gasto_firmas",
                "gc_service", "gc_mecanica", "gc_chapa_pintura", "gc_tapizado",
                "gc_neumaticos", "gc_vidrios", "gc_cerrajeria", "gc_lavado",
                "gc_gnc", "gc_grabado_autopartes", "gc_vtv", "gc_verificacion", "gc_patentes", "gc_otros",
                "total_gastos",
            ]
            for campo in campos_a_preservar:
                gastos_preservar[campo] = getattr(ficha, campo, None)

            # Valor anterior del monto adeudado de patentes, para decidir si
            # corresponde re-sincronizar gasto_patentes (ver más abajo).
            _patentes_monto_old = getattr(ficha, "patentes_monto", None)

            # Lista de campos de gasto que están en el form: si el POST no los
            # mandó (porque el form de edición no incluye la sección de gastos),
            # NO los pisamos con 0 al guardar.
            campos_form_recibidos = set(ficha_form.cleaned_data.keys())

            ficha = ficha_form.save(commit=False)

            # Restaurar gastos cuando:
            #   - el form NO recibió ese campo (no estaba en el POST), o
            #   - el form mandó None / 0 pero el valor anterior era > 0
            # Esto evita que ediciones parciales de la ficha zerifiquen los
            # gastos cargados.
            # Cuando el POST viene del editor de gastos (modal completo) trae el
            # marcador "gastos_editables": ahí el usuario PUEDE poner un gasto en
            # 0 a propósito, así que NO restauramos el valor anterior si el campo
            # vino en el form. Sin marcador, se mantiene la protección (otras
            # pestañas no pueden zerificar los gastos por accidente).
            gastos_editables = bool(request.POST.get("gastos_editables"))
            for campo, valor_previo in gastos_preservar.items():
                if valor_previo is None or valor_previo == 0:
                    continue
                if campo not in campos_form_recibidos:
                    # No vino en el POST (otra pestaña) → preservar siempre.
                    setattr(ficha, campo, valor_previo)
                    continue
                nuevo = getattr(ficha, campo, None)
                if (nuevo is None or nuevo == 0) and not gastos_editables:
                    # Vino en 0 pero sin edición explícita de gastos → preservar.
                    setattr(ficha, campo, valor_previo)

            # ===============================
            # CAMPOS MANUALES (NO ESTÁN EN EL FORM)
            # ===============================
            ficha.titulo_estado = request.POST.get("titulo_estado") or ficha.titulo_estado
            ficha.titulo_obs = request.POST.get("titulo_obs") or ficha.titulo_obs
            ficha.cedula_check_estado = request.POST.get("cedula_check_estado") or ficha.cedula_check_estado
            ficha.cedula_check_obs = request.POST.get("cedula_check_obs") or ficha.cedula_check_obs
            ficha.prenda_estado = request.POST.get("prenda_estado") or ficha.prenda_estado
            ficha.prenda_obs = request.POST.get("prenda_obs") or ficha.prenda_obs

            # Gastos concesionario: tomamos el valor del POST tal cual.
            # Si el usuario manda 0, el campo se va a 0 (y el signal
            # se encarga de remover el GastoReporteInterno asociado).
            # Si el campo no viene en el POST, no se toca.
            campos_gc = [
                "gc_service", "gc_mecanica", "gc_chapa_pintura", "gc_tapizado",
                "gc_neumaticos", "gc_vidrios", "gc_cerrajeria", "gc_lavado",
                "gc_gnc", "gc_grabado_autopartes", "gc_vtv", "gc_verificacion", "gc_patentes", "gc_otros",
            ]
            gc_invalidos = []
            for campo in campos_gc:
                if campo not in request.POST:
                    continue
                valor_raw = (request.POST.get(campo, "") or "").replace(",", ".").strip()
                try:
                    nuevo = Decimal(valor_raw) if valor_raw else Decimal("0")
                except Exception:
                    # Monto mal formateado: NO lo guardamos, pero avisamos para
                    # que el usuario no crea que se guardó.
                    gc_invalidos.append(campo.replace("gc_", "").replace("_", " "))
                    continue
                setattr(ficha, campo, nuevo)
            if gc_invalidos:
                messages.warning(
                    request,
                    "Estos montos de gastos de concesionario tenían un formato "
                    "inválido y no se guardaron: " + ", ".join(gc_invalidos) + "."
                )

            # Vincular el "Monto adeudado" de patentes con el gasto de ingreso
            # de Patentes (la deuda de patentes es un gasto de ingreso).
            # ⚠️ SOLO sincronizamos cuando el monto de patentes CAMBIÓ en este
            # guardado, o cuando gasto_patentes todavía estaba vacío. Así no
            # pisamos un gasto_patentes ajustado a mano en cada guardado de la
            # pestaña Documentación (el select patentes_adeuda viaja siempre).
            if "patentes_adeuda" in request.POST and ficha.patentes_adeuda == "si":
                monto_nuevo = ficha.patentes_monto or Decimal("0")
                monto_old = _patentes_monto_old or Decimal("0")
                gasto_pat_old = gastos_preservar.get("gasto_patentes") or Decimal("0")
                if monto_nuevo != monto_old or gasto_pat_old == 0:
                    ficha.gasto_patentes = monto_nuevo

            # Un 0km NO tiene gastos de ingreso: se fuerzan a 0.
            if vehiculo_guardado.es_0km:
                for _g in ("gasto_f08", "gasto_informes", "gasto_patentes",
                           "gasto_infracciones", "gasto_verificacion", "gasto_autopartes",
                           "gasto_vtv", "gasto_r541", "gasto_firmas"):
                    setattr(ficha, _g, Decimal("0"))

            ficha.save()

            # Patentes mensuales vencidas (posteriores al ingreso) → se acumulan
            # automáticamente en gastos de concesionario al guardar la ficha.
            from vehiculos.services import acumular_patentes_mensuales
            if acumular_patentes_mensuales(ficha):
                ficha.save(update_fields=["gc_patentes"])

            # ===============================
            # GUARDAR FICHA TÉCNICA
            # ===============================
            if ficha_tecnica_form is not None and ficha_tecnica_form.is_valid():
                ficha_tecnica_form.save()

            # ===============================
            # POST-GUARDADO
            # ===============================
            calcular_total_gastos(ficha)
            sincronizar_turnos_calendario(vehiculo, ficha)
            from vehiculos.services import recalcular_cuentas_vinculadas
            recalcular_cuentas_vinculadas(vehiculo)

            messages.success(request, "Cambios guardados correctamente.")
            return redirect(
                "vehiculos:ficha_completa",
                vehiculo_id=vehiculo.id
            )

        # ❌ Formularios inválidos — mostramos el motivo real
        errores = []
        for form in (vehiculo_form, ficha_form):
            for errs in form.errors.values():
                errores.extend(str(e) for e in errs)
        messages.error(request, " ".join(errores) if errores else "Error al guardar los cambios.")
        return redirect(
            "vehiculos:ficha_completa",
            vehiculo_id=vehiculo.id
        )

    # ❌ Si no es POST
    return redirect("vehiculos:lista_vehiculos")


# ============================================
# FICHA COMPLETA – DEFINITIVA
# ============================================
def ficha_completa(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)
    ficha_tec, _ = FichaTecnica.objects.get_or_create(vehiculo=vehiculo)

    # 🔴 AGREGADO MÍNIMO PARA QUE SE RENDERICEN LAS FECHAS
    ficha_form = FichaVehicularForm(instance=ficha)
    vehiculo_form = VehiculoForm(instance=vehiculo)
    ficha_tecnica_form = FichaTecnicaForm(instance=ficha_tec)

    CONCEPTOS = {
        "f08": "Formulario 08",
        "informes": "Informes",
        "patentes": "Patentes",
        "infracciones": "Infracciones",
        "verificacion": "Verificación",
        "autopartes": "Autopartes",
        "vtv": "VTV",
        "r541": "R541",
        "firmas": "Firmas",
    }

    mapa_gastos = {
        "f08": ficha.gasto_f08,
        "informes": ficha.gasto_informes,
        "patentes": ficha.gasto_patentes,
        "infracciones": ficha.gasto_infracciones,
        "verificacion": ficha.gasto_verificacion,
        "autopartes": ficha.gasto_autopartes,
        "vtv": ficha.gasto_vtv,
        "r541": ficha.gasto_r541,
        "firmas": ficha.gasto_firmas,
    }

    gastos_ingreso = []

    for key, monto in mapa_gastos.items():
        if monto is None:
            continue

        monto = Decimal(monto)
        if monto <= 0:
            continue

        # Saldo del vehículo = deuda con el ENTE. Solo lo bajan los pagos en
        # los que el ente quedó pagado (prov_directo, cli_directo, cli_adelanto,
        # prov_reintegro).
        total_pagado = (
            PagoGastoIngreso.objects.filter(
                vehiculo=vehiculo,
                concepto=key,
                situacion__in=["prov_directo", "cli_directo", "cli_adelanto", "prov_reintegro"],
            ).aggregate(total=Sum("monto"))["total"]
            or Decimal("0")
        )

        saldo = monto - Decimal(total_pagado)

        # Cobrado al cliente pero todavía no pagado al organismo (situación 2):
        # impaga por concesionario. Se muestra como informativo.
        cobrado_informativo = (
            PagoGastoIngreso.objects.filter(
                vehiculo=vehiculo,
                concepto=key,
                situacion="cli_concesion",
            ).aggregate(total=Sum("monto"))["total"]
            or Decimal("0")
        )

        # 🆕 OBTENER HISTORIAL DE PAGOS DE ESTE CONCEPTO (todos)
        pagos = PagoGastoIngreso.objects.filter(
            vehiculo=vehiculo,
            concepto=key
        ).order_by('-fecha_pago')

        # 🔴 SI EL SALDO ES 0, MARCAMOS COMO PAGADO PERO LO MOSTRAMOS
        esta_pagado = saldo <= 0

        gastos_ingreso.append({
            "key": key,
            "concepto": CONCEPTOS[key],
            "monto": monto,
            "total_pagado": total_pagado,
            "cobrado_informativo": cobrado_informativo,
            "saldo": saldo,
            "pagos": pagos,
            "esta_pagado": esta_pagado,
            "ente_sugerido": ENTE_SUGERIDO.get(key, ""),
        })

    total_pendiente = sum(
        (g["saldo"] for g in gastos_ingreso if g["saldo"] > 0),
        Decimal("0")
    )

    # =============================
    # GASTOS DE CONCESIONARIO
    # =============================
    GASTOS_CONC_CAMPOS = [
        ("gc_service", "Service"),
        ("gc_mecanica", "Mecanica"),
        ("gc_chapa_pintura", "Chapa y pintura"),
        ("gc_tapizado", "Tapizado"),
        ("gc_neumaticos", "Neumaticos"),
        ("gc_vidrios", "Vidrios"),
        ("gc_cerrajeria", "Cerrajeria"),
        ("gc_lavado", "Lavado / Pulido"),
        ("gc_gnc", "GNC"),
        ("gc_grabado_autopartes", "Grabado autopartes"),
        ("gc_vtv", "VTV"),
        ("gc_verificacion", "Verificacion policial"),
        ("gc_patentes", "Patentes"),
        ("gc_otros", "Otros"),
    ]

    gastos_conc_items = []
    total_gastos_conc = Decimal("0")
    for campo, label in GASTOS_CONC_CAMPOS:
        monto = getattr(ficha, campo, None) or Decimal("0")
        gastos_conc_items.append({"campo": campo, "label": label, "monto": monto})
        total_gastos_conc += Decimal(monto)

    # Gastos extras (modelo GastoConcesionario)
    gastos_extras = GastoConcesionario.objects.filter(vehiculo=vehiculo)
    total_extras = gastos_extras.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    total_gastos_conc += total_extras

    # Pago de gastos de concesionario (mismo patrón que gastos de ingreso)
    ctx_pago_conc = construir_gastos_conc_pago(vehiculo, ficha, gastos_extras)

    return render(
        request,
        "vehiculos/ficha_completa.html",
        {
            "vehiculo": vehiculo,
            "vehiculo_form": vehiculo_form,
            "ficha": ficha,
            "ficha_form": ficha_form,
            "gastos_ingreso": gastos_ingreso,
            "total_pendiente": total_pendiente,
            "gastos_conc_items": gastos_conc_items,
            "gastos_extras": gastos_extras,
            "total_gastos_conc": total_gastos_conc,
            "total_extras": total_extras,
            "ficha_tecnica_form": ficha_tecnica_form,
            "clientes_titular": _clientes_para_titular(),
            "tiene_proveedor": ficha.vendedor_id is not None,
            **ctx_pago_conc,
        },
    )


# ==========================================================
# GUARDAR GASTOS DE CONCESIONARIO (CAMPOS FIJOS)
# ==========================================================
@login_required
def guardar_gastos_concesionario(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    if request.method == "POST":
        campos_gc = [
            "gc_service", "gc_mecanica", "gc_chapa_pintura", "gc_tapizado",
            "gc_neumaticos", "gc_vidrios", "gc_cerrajeria", "gc_lavado",
            "gc_gnc", "gc_grabado_autopartes", "gc_vtv", "gc_verificacion", "gc_patentes", "gc_otros",
        ]

        gc_patentes_old = ficha.gc_patentes or Decimal("0")
        gc_invalidos = []
        for campo in campos_gc:
            if campo not in request.POST:
                # El campo no vino en el POST: no tocar el valor guardado.
                continue
            valor_raw = (request.POST.get(campo, "") or "").replace(",", ".").strip()
            try:
                nuevo = Decimal(valor_raw) if valor_raw else Decimal("0")
            except Exception:
                gc_invalidos.append(campo.replace("gc_", "").replace("_", " "))
                continue
            # Tomamos el valor del form tal cual: si manda 0, se borra a 0.
            setattr(ficha, campo, nuevo)

        # Si el usuario BAJÓ gc_patentes a mano (lo borró/redujo), marcamos que es
        # manual para que la acumulación automática de patentes no lo re-infle.
        campos_guardar = list(campos_gc)
        if "gc_patentes" in request.POST and (ficha.gc_patentes or Decimal("0")) < gc_patentes_old:
            ficha.gc_patentes_manual = True
            campos_guardar.append("gc_patentes_manual")

        if gc_invalidos:
            messages.warning(
                request,
                "Estos montos tenían un formato inválido y no se guardaron: "
                + ", ".join(gc_invalidos) + "."
            )
        ficha.save(update_fields=campos_guardar)
        from vehiculos.services import recalcular_cuentas_vinculadas
        recalcular_cuentas_vinculadas(vehiculo)
        messages.success(request, "Gastos de concesionario actualizados.")

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)


# ==========================================================
# AGREGAR GASTO EXTRA DE CONCESIONARIO
# ==========================================================
@login_required
def agregar_gasto_extra(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method == "POST":
        concepto = request.POST.get("concepto", "").strip()
        monto_raw = request.POST.get("monto", "0").replace(",", ".")
        observaciones = request.POST.get("observaciones", "").strip()

        if not concepto:
            messages.error(request, "El concepto es obligatorio.")
            return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

        try:
            monto = Decimal(monto_raw)
        except Exception:
            messages.error(request, "Monto invalido.")
            return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

        GastoConcesionario.objects.create(
            vehiculo=vehiculo,
            concepto=concepto,
            monto=monto,
            observaciones=observaciones,
        )
        messages.success(request, f"Gasto \"{concepto}\" agregado.")

    # Redirige a la sección de gastos adicionales para que el usuario vea
    # el nuevo registro y su botón eliminar (estaba más abajo en la ficha).
    return redirect(reverse("vehiculos:ficha_completa", args=[vehiculo.id]) + "#gastos-adicionales")


# ==========================================================
# ELIMINAR GASTO EXTRA DE CONCESIONARIO
# ==========================================================
@login_required
def eliminar_gasto_extra(request, pk):
    gasto = get_object_or_404(GastoConcesionario, pk=pk)
    vehiculo_id = gasto.vehiculo_id

    if request.method == "POST":
        gasto.delete()
        messages.success(request, "Gasto eliminado.")

    return redirect(reverse("vehiculos:ficha_completa", args=[vehiculo_id]) + "#gastos-adicionales")


# ==========================================================
# TOGGLE "VAN A VENIR A VERLO" (visita pendiente)
# ==========================================================
@login_required
def toggle_visita_vehiculo(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    if request.method == "POST":
        vehiculo.visita_pendiente = not vehiculo.visita_pendiente
        vehiculo.save(update_fields=["visita_pendiente"])
    return redirect(request.META.get("HTTP_REFERER") or "vehiculos:lista_vehiculos")


# ==========================================================
# AGREGAR GASTO INGRESO (CUENTA CORRIENTE)
# ==========================================================
@transaction.atomic
def agregar_gasto_ingreso(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    _venta = getattr(vehiculo, "venta", None)
    cuenta = getattr(_venta, "cuenta_corriente", None) if _venta else None
    if cuenta is None:
        messages.error(request, "Este vehículo no tiene una cuenta corriente asociada.")
        return redirect(request.META.get("HTTP_REFERER") or "vehiculos:lista_vehiculos")

    if request.method == "POST":
        from cuentas.models import MovimientoCuenta

        descripcion = request.POST.get("descripcion")
        monto = Decimal(request.POST.get("monto"))

        MovimientoCuenta.objects.create(
            cuenta=cuenta,
            vehiculo=vehiculo,
            descripcion=descripcion,
            tipo="debe",
            monto=monto,
            origen="permuta"
        )

        cuenta.recalcular_saldo()
        messages.success(request, "Gasto de ingreso cargado correctamente.")

        return redirect(
            "cuentas:cuenta_corriente_detalle",
            cuenta_id=cuenta.id
        )

    return render(
        request,
        "vehiculos/agregar_gasto_ingreso.html",
        {"vehiculo": vehiculo},
    )


# ==========================================================
# PDF DE GASTOS DE INGRESO (desde la ficha del vehículo)
# ==========================================================
def gastos_ingreso_pdf(request, vehiculo_id):
    from reportes.pdf_utils import render_pdf_listado

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha = getattr(vehiculo, "ficha", None)

    def money(v):
        try:
            return f"$ {Decimal(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "$ 0,00"

    filas = []
    total = Decimal("0")
    total_pagado = Decimal("0")
    total_saldo = Decimal("0")
    if ficha:
        for concepto, monto in ficha.mapa_gastos_ingreso().items():
            m = Decimal(monto or 0)
            # Pago registrado (lo que salda la ficha) y saldo restante.
            pagado = ficha.total_pagado_por_concepto(concepto)
            saldo = m - pagado
            filas.append([
                concepto,
                money(m),
                money(pagado) if pagado > 0 else "—",
                money(saldo),
            ])
            total += m
            total_pagado += pagado
            total_saldo += saldo

    dominio = getattr(vehiculo, "dominio", "") or "—"
    return render_pdf_listado(
        filename=f"gastos_ingreso_{vehiculo_id}.pdf",
        titulo="Gastos de ingreso",
        subtitulo=f"{vehiculo.marca} {vehiculo.modelo} — {dominio}",
        # Se muestra el gasto total y, como aclaración, el pago registrado
        # descontado y el saldo pendiente.
        columnas=["Concepto", "Gasto total", "Pagado", "Saldo"],
        filas=filas,
        totales=["TOTAL", money(total), money(total_pagado), money(total_saldo)],
    )


def gastos_adeudados_pdf(request, vehiculo_id):
    """
    PDF de lo que se adeuda de los gastos de ingreso de un vehículo:
    por cada concepto muestra monto, total pagado y saldo pendiente.
    """
    from reportes.pdf_utils import render_pdf_listado

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha = getattr(vehiculo, "ficha", None)

    def money(v):
        try:
            return f"$ {Decimal(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "$ 0,00"

    CONCEPTOS = {
        "f08": "Formulario 08",
        "informes": "Informes",
        "patentes": "Patentes",
        "infracciones": "Infracciones",
        "verificacion": "Verificación",
        "autopartes": "Autopartes",
        "vtv": "VTV",
        "r541": "R541",
        "firmas": "Firmas",
    }

    filas = []
    total_adeudado = Decimal("0")
    if ficha:
        mapa = {
            "f08": ficha.gasto_f08,
            "informes": ficha.gasto_informes,
            "patentes": ficha.gasto_patentes,
            "infracciones": ficha.gasto_infracciones,
            "verificacion": ficha.gasto_verificacion,
            "autopartes": ficha.gasto_autopartes,
            "vtv": ficha.gasto_vtv,
            "r541": ficha.gasto_r541,
            "firmas": ficha.gasto_firmas,
        }
        for key, monto in mapa.items():
            if monto is None:
                continue
            monto = Decimal(monto)
            if monto <= 0:
                continue
            pagado = (
                PagoGastoIngreso.objects.filter(
                    vehiculo=vehiculo, concepto=key, mantiene_deuda_vehiculo=False
                )
                .aggregate(total=Sum("monto"))["total"]
                or Decimal("0")
            )
            saldo = monto - Decimal(pagado)
            if saldo <= 0:
                continue  # solo lo que se adeuda
            total_adeudado += saldo
            filas.append([
                CONCEPTOS.get(key, key),
                money(monto),
                money(pagado),
                money(saldo),
            ])

    dominio = getattr(vehiculo, "dominio", "") or "—"
    return render_pdf_listado(
        filename=f"adeudado_gastos_{vehiculo_id}.pdf",
        titulo="Saldo adeudado — Gastos de ingreso",
        subtitulo=f"{vehiculo.marca} {vehiculo.modelo} — {dominio}",
        columnas=["Concepto", "Monto", "Pagado", "Saldo"],
        filas=filas,
        totales=["TOTAL ADEUDADO", "", "", money(total_adeudado)],
    )


# ==========================================================
# REGISTRAR PAGO DE GASTO DE INGRESO (DEFINITIVO)
# ==========================================================
from cuentas.models import MovimientoCuenta


CONCEPTOS_GASTO = {
    "f08": "Formulario 08",
    "informes": "Informes",
    "patentes": "Patentes",
    "infracciones": "Infracciones",
    "verificacion": "Verificación",
    "autopartes": "Autopartes",
    "vtv": "VTV",
    "r541": "R541",
    "firmas": "Firmas",
}

# Sugerencia inicial del ente según el concepto (editable por el usuario).
ENTE_SUGERIDO = {
    "f08": "Registro",
    "informes": "Registro",
    "patentes": "Patentes / Rentas",
    "infracciones": "Infracciones",
    "verificacion": "Verificación policial",
    "autopartes": "Grabado de autopartes",
    "vtv": "VTV",
    "r541": "R-541",
    "firmas": "Escribanía",
}

# Situaciones en las que el ENTE quedó efectivamente pagado (el gasto deja de
# ser deuda del vehículo con el ente). En cli_concesion y pendiente el ente
# todavía NO está pagado.
SITUACIONES_ENTE_PAGADO = {"prov_directo", "cli_directo", "cli_adelanto", "prov_reintegro"}

# Situaciones donde el circuito queda totalmente cerrado al registrar el pago.
SITUACIONES_SALDADAS = {"prov_directo", "cli_directo"}

SITUACIONES_PROVEEDOR = {"prov_directo", "prov_reintegro"}
SITUACIONES_CLIENTE = {"cli_directo", "cli_concesion", "cli_adelanto", "pendiente"}


@csrf_exempt
@transaction.atomic
def registrar_pago_gasto(request):
    if request.method != "POST":
        return redirect("vehiculos:inicio")

    from compraventa.models import ReintegroProveedor

    vehiculo_id = request.POST.get("vehiculo_id")
    concepto_key = (request.POST.get("gasto_id") or "").strip()
    fecha_pago = request.POST.get("fecha_pago")
    monto_raw = request.POST.get("monto")
    observaciones = request.POST.get("observaciones") or ""
    situacion = (request.POST.get("situacion") or "").strip()
    ente = (request.POST.get("ente") or "").strip()

    # ── Validaciones básicas ──
    if not vehiculo_id:
        messages.error(request, "Vehículo inválido.")
        return redirect(request.META.get("HTTP_REFERER"))
    if not monto_raw:
        messages.error(request, "El monto del pago debe ser mayor a 0.")
        return redirect(request.META.get("HTTP_REFERER"))
    if not fecha_pago:
        messages.error(request, "Para registrar un pago es obligatorio ingresar la fecha.")
        return redirect(request.META.get("HTTP_REFERER"))

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha = vehiculo.ficha

    if concepto_key not in CONCEPTOS_GASTO:
        messages.error(request, "Concepto de gasto inválido.")
        return redirect(request.META.get("HTTP_REFERER"))

    try:
        monto = Decimal(str(monto_raw).replace(",", "."))
    except (ValueError, InvalidOperation):
        messages.error(request, "Monto inválido.")
        return redirect(request.META.get("HTTP_REFERER"))
    if monto <= 0:
        messages.error(request, "El monto del pago debe ser mayor a 0.")
        return redirect(request.META.get("HTTP_REFERER"))

    # ── La situación elegida define a quién pertenece el gasto ──
    # prov_* = lo asume el proveedor (me lo reintegra / pagó él);
    # cli_*/pendiente = lo asume el cliente.
    # Ya NO depende de Titularidad: cualquier gasto puede marcarse como
    # "lo pagué yo y el proveedor me reintegra".
    if situacion in SITUACIONES_PROVEEDOR:
        pertenece = "proveedor"
    elif situacion in SITUACIONES_CLIENTE:
        pertenece = "cliente"
    else:
        messages.error(request, "Elegí una situación válida para este pago.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

    # Para el reintegro necesitamos saber QUÉ proveedor me debe.
    proveedor = _proveedor_de_vehiculo(vehiculo, ficha)
    if situacion == "prov_reintegro" and proveedor is None:
        messages.error(
            request,
            "Para marcar que el proveedor te reintegra, primero cargá el "
            "proveedor del vehículo en la pestaña Titularidad."
        )
        return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

    saldado = situacion in SITUACIONES_SALDADAS
    label = CONCEPTOS_GASTO[concepto_key]

    # ── Crear el registro del pago (lo único que se mueve) ──
    pago = PagoGastoIngreso.objects.create(
        vehiculo=vehiculo,
        concepto=concepto_key,
        fecha_pago=fecha_pago,
        monto=monto,
        observaciones=observaciones,
        pertenece=pertenece,
        situacion=situacion,
        ente=ente,
        saldado=saldado,
        fecha_saldado=fecha_pago if saldado else None,
        # compatibilidad legado mientras convive el boolean
        mantiene_deuda_vehiculo=(situacion == "cli_concesion"),
    )

    marca = f"[GI:{pago.pk}]"
    # ¿A qué cuenta corriente pertenece este gasto? Bug #3:
    # Si el vehículo fue ENTREGADO (permuta) en alguna cuenta, la deuda del
    # gasto adelantado es de QUIEN LO ENTREGÓ → esa cuenta. Solo si el vehículo
    # no es permuta de nadie, usamos la venta (el comprador).
    cuenta = None
    from cuentas.models import MovimientoCuenta
    perm_mov = (
        MovimientoCuenta.objects
        .filter(vehiculo=vehiculo, origen="permuta")
        .select_related("cuenta")
        .first()
    )
    if perm_mov is not None:
        cuenta = perm_mov.cuenta
    else:
        _venta = getattr(vehiculo, "venta", None)
        if _venta is not None:
            cuenta = getattr(_venta, "cuenta_corriente", None)

    # ── Efectos por situación (atómico) ──
    if situacion == "prov_reintegro":
        # B) Lo pagué yo y el proveedor me reintegra → plata aparte.
        rein = ReintegroProveedor.objects.create(
            proveedor=proveedor,
            vehiculo=vehiculo,
            concepto=concepto_key,
            ente=ente,
            monto=monto,
            estado="pendiente",
        )
        pago.reintegro_proveedor_id = rein.pk
        pago.save(update_fields=["reintegro_proveedor_id"])

    elif situacion == "cli_adelanto":
        # 3) Adelanté yo al organismo → el cliente me debe ese gasto (debe).
        if cuenta:
            mov = MovimientoCuenta.objects.create(
                cuenta=cuenta, vehiculo=vehiculo,
                descripcion=f"Gasto de ingreso adelantado: {label} — el cliente lo debe {marca}",
                tipo="debe", monto=monto, origen="manual",
            )
            pago.movimiento_cuenta_id = mov.pk
            pago.save(update_fields=["movimiento_cuenta_id"])
            cuenta.recalcular_saldo()

    elif situacion == "cli_concesion":
        # 2) El cliente me pagó pero todavía no pagué al organismo. Reflejar la plata
        #    real que entró: el gasto como deuda (debe) + el pago del cliente
        #    (haber) → neto 0 en la cuenta, pero queda registrado el cobro.
        #    La deuda con el ente queda como "impaga por concesionario" (cálculo).
        if cuenta:
            mov_debe = MovimientoCuenta.objects.create(
                cuenta=cuenta, vehiculo=vehiculo,
                descripcion=f"Gasto de ingreso: {label} {marca}",
                tipo="debe", monto=monto, origen="manual",
            )
            MovimientoCuenta.objects.create(
                cuenta=cuenta, vehiculo=vehiculo,
                descripcion=f"Pago del cliente por {label} (pendiente de pagar al organismo) {marca}",
                tipo="haber", monto=monto, origen="manual",
            )
            pago.movimiento_cuenta_id = mov_debe.pk
            pago.save(update_fields=["movimiento_cuenta_id"])
            cuenta.recalcular_saldo()

    # prov_directo / cli_directo / pendiente → no crean registros adicionales.

    # ── Mensajes ──
    if situacion == "cli_concesion":
        messages.success(
            request,
            f"Pago registrado. {label}: ${monto}. El cliente te pagó; "
            "queda como IMPAGA POR CONCESIONARIO hasta que le pagues al organismo."
        )
    elif situacion == "cli_adelanto":
        messages.success(request, f"Pago registrado. {label}: ${monto}. El cliente te debe este gasto.")
    elif situacion == "prov_reintegro":
        messages.success(request, f"Pago registrado. {label}: ${monto}. El proveedor te debe el reintegro.")
    else:
        messages.success(request, f"Pago registrado y saldado. {label}: ${monto}.")

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)


def proveedor_id_de(ficha):
    """True si la ficha tiene proveedor cargado en Titularidad."""
    return getattr(ficha, "vendedor_id", None) is not None


def _proveedor_de_vehiculo(vehiculo, ficha):
    """
    Resuelve el proveedor de un vehículo para los reintegros.
    Primero mira Titularidad (ficha.vendedor); si no hay, busca la operación
    de compra-venta cargada para ese vehículo.
    """
    if getattr(ficha, "vendedor_id", None):
        return ficha.vendedor
    try:
        from compraventa.models import CompraVentaOperacion
        op = (
            CompraVentaOperacion.objects
            .filter(vehiculo=vehiculo, proveedor__isnull=False)
            .select_related("proveedor")
            .first()
        )
        return op.proveedor if op else None
    except Exception:
        return None


# ==========================================================
# REGISTRAR PAGOS DE VARIOS GASTOS DE UNA VEZ
# ==========================================================
@login_required
@transaction.atomic
def registrar_pagos_gastos_lote(request):
    if request.method != "POST":
        return redirect("vehiculos:inicio")

    vehiculo_id = request.POST.get("vehiculo_id")
    fecha_pago = request.POST.get("fecha_pago_lote")
    observaciones_comunes = (request.POST.get("observaciones_lote") or "").strip()
    mantiene_deuda = request.POST.get("mantiene_deuda") == "1"

    if not vehiculo_id or not fecha_pago:
        messages.error(request, "Faltan datos para registrar los pagos.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    try:
        ficha = vehiculo.ficha
    except FichaVehicular.DoesNotExist:
        messages.error(request, "El vehículo no tiene ficha vehicular.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

    CONCEPTOS = {
        "f08": "Formulario 08",
        "informes": "Informes",
        "patentes": "Patentes",
        "infracciones": "Infracciones",
        "verificacion": "Verificación",
        "autopartes": "Autopartes",
        "vtv": "VTV",
        "r541": "R541",
        "firmas": "Firmas",
    }

    mapa_gastos = {
        "f08": ficha.gasto_f08, "informes": ficha.gasto_informes,
        "patentes": ficha.gasto_patentes, "infracciones": ficha.gasto_infracciones,
        "verificacion": ficha.gasto_verificacion, "autopartes": ficha.gasto_autopartes,
        "vtv": ficha.gasto_vtv, "r541": ficha.gasto_r541, "firmas": ficha.gasto_firmas,
    }

    cuenta = None
    if hasattr(vehiculo, "venta") and vehiculo.venta:
        if hasattr(vehiculo.venta, "cuenta_corriente"):
            cuenta = vehiculo.venta.cuenta_corriente

    creados = 0
    saltados = []

    for key, label in CONCEPTOS.items():
        monto_raw = (request.POST.get(f"monto_{key}") or "").strip()
        if not monto_raw:
            continue
        try:
            monto = Decimal(monto_raw)
        except Exception:
            saltados.append(f"{label} (monto inválido)")
            continue
        if monto <= 0:
            continue

        monto_total = mapa_gastos.get(key) or Decimal("0")
        ya_pagado = (
            PagoGastoIngreso.objects.filter(
                vehiculo=vehiculo, concepto=key,
                situacion__in=["prov_directo", "cli_directo", "cli_adelanto", "prov_reintegro"],
            )
            .aggregate(total=Sum("monto"))["total"] or Decimal("0")
        )
        saldo = Decimal(monto_total) - Decimal(ya_pagado)
        if not mantiene_deuda:
            if saldo <= 0:
                saltados.append(f"{label} (ya pagado)")
                continue
            if monto > saldo:
                monto = saldo

        # Situación según proveedor en Titularidad. En lote: pagos directos
        # (saldados) salvo que se tilde "cliente me pagó, no pagué al organismo".
        if ficha.vendedor_id:
            pertenece, situacion = "proveedor", "prov_directo"
        elif mantiene_deuda:
            pertenece, situacion = "cliente", "cli_concesion"
        else:
            pertenece, situacion = "cliente", "cli_directo"
        saldado = situacion in ("prov_directo", "cli_directo")

        pago = PagoGastoIngreso.objects.create(
            vehiculo=vehiculo,
            concepto=key,
            fecha_pago=fecha_pago,
            monto=monto,
            observaciones=observaciones_comunes,
            pertenece=pertenece,
            situacion=situacion,
            ente=ENTE_SUGERIDO.get(key, ""),
            saldado=saldado,
            fecha_saldado=fecha_pago if saldado else None,
            mantiene_deuda_vehiculo=(situacion == "cli_concesion"),
        )
        creados += 1

        # Situación 2 en lote: reflejar el cobro del cliente (debe + haber).
        if situacion == "cli_concesion" and cuenta:
            marca = f"[GI:{pago.pk}]"
            mov_debe = MovimientoCuenta.objects.create(
                cuenta=cuenta, vehiculo=vehiculo,
                descripcion=f"Gasto de ingreso: {label} {marca}",
                tipo="debe", monto=monto, origen="manual",
            )
            MovimientoCuenta.objects.create(
                cuenta=cuenta, vehiculo=vehiculo,
                descripcion=f"Pago del cliente por {label} (pendiente de pagar al organismo) {marca}",
                tipo="haber", monto=monto, origen="manual",
            )
            pago.movimiento_cuenta_id = mov_debe.pk
            pago.save(update_fields=["movimiento_cuenta_id"])

    if cuenta:
        cuenta.recalcular_saldo()

    if creados:
        msg = f"Se registraron {creados} pago(s) en lote."
        if saltados:
            msg += f" Salteados: {', '.join(saltados)}."
        messages.success(request, msg)
    else:
        messages.warning(
            request,
            "No se registró ningún pago. Completá al menos un monto."
        )

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)


# ==========================================================
# AGREGAR GASTO IMPAGO (situación 2) A AGENDA DE PAGOS — con confirmación
# ==========================================================
@login_required
@transaction.atomic
def agregar_gasto_a_agenda(request, pago_id):
    """
    Crea un PagoFuturo (Agenda de Pagos) por un gasto en situación 2
    (cliente me pagó, todavía no pagué al organismo). Solo por POST (confirmación).
    Guarda la referencia para poder revertir.
    """
    pago = get_object_or_404(PagoGastoIngreso, id=pago_id)
    if request.method != "POST":
        return redirect("vehiculos:ficha_completa", vehiculo_id=pago.vehiculo_id)

    if pago.situacion != "cli_concesion":
        messages.error(request, "Este pago no corresponde a una deuda impaga por concesionario.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=pago.vehiculo_id)

    if pago.pago_futuro_id:
        messages.info(request, "Este gasto ya está en la Agenda de Pagos.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=pago.vehiculo_id)

    from agenda_pagos.models import PagoFuturo

    label = CONCEPTOS_GASTO.get(pago.concepto, pago.concepto)
    veh = pago.vehiculo
    ente = pago.ente or "organismo"

    pf = PagoFuturo.objects.create(
        descripcion=f"Gasto de ingreso {label} – {veh} (pagar a {ente})",
        monto=pago.monto,
        fecha_vencimiento=pago.fecha_pago,
        destino="control_gastos",
        observaciones=(
            f"Origen: vehículo #{veh.id} {veh} ({veh.dominio or 's/dominio'}). "
            f"Cobrado al cliente, pendiente de pagar al organismo {ente}."
        ),
        creado_por=request.user if request.user.is_authenticated else None,
    )
    pago.pago_futuro_id = pf.pk
    pago.save(update_fields=["pago_futuro_id"])

    messages.success(
        request,
        f"«{label}» agregado a la Agenda de Pagos (vence {pago.fecha_pago:%d/%m/%Y})."
    )
    return redirect("vehiculos:ficha_completa", vehiculo_id=pago.vehiculo_id)


# ==========================================================
# RECIBO DE UN PAGO DE GASTO DE INGRESO (PDF)
# ==========================================================
@login_required
def recibo_gasto_ingreso_pdf(request, pago_id):
    pago = get_object_or_404(PagoGastoIngreso, id=pago_id)
    from reportes.pdf_utils import render_pdf_listado

    v = pago.vehiculo
    veh = f"{v.marca} {v.modelo}"
    if v.dominio:
        veh += f" ({v.dominio})"
    concepto = CONCEPTOS_GASTO.get(pago.concepto, pago.concepto)

    filas = [
        ["Vehículo", veh],
        ["Concepto", concepto],
        ["Importe", f"$ {pago.monto:,.0f}".replace(",", ".")],
        ["Fecha de pago", pago.fecha_pago.strftime("%d/%m/%Y") if pago.fecha_pago else "—"],
        ["Ente / organismo", pago.ente or "—"],
        ["Situación", pago.get_situacion_display()],
    ]
    if pago.observaciones:
        filas.append(["Observaciones", pago.observaciones])

    return render_pdf_listado(
        filename=f"recibo_gasto_ingreso_{pago.id}.pdf",
        titulo="Recibo de pago — Gasto de ingreso",
        subtitulo="AMICHETTI AUTOMOTORES",
        columnas=["Concepto", "Detalle"],
        filas=filas,
    )


# ==========================================================
# ELIMINAR PAGO DE GASTO DE INGRESO
# ==========================================================
@login_required
@transaction.atomic
def eliminar_pago_gasto(request, pago_id):
    pago = get_object_or_404(PagoGastoIngreso, id=pago_id)
    vehiculo_id = pago.vehiculo_id

    if request.method == "POST":
        # Revertir lo que el pago haya generado en otros módulos:
        # - movimientos en la cuenta corriente (marcados con [GI:pk])
        # - reintegro del proveedor
        # - pago futuro en Agenda de Pagos
        from cuentas.models import MovimientoCuenta as _Mov
        cuenta = None
        movs = _Mov.objects.filter(descripcion__contains=f"[GI:{pago.pk}]")
        for m in movs:
            cuenta = m.cuenta
        movs.delete()
        if cuenta:
            cuenta.recalcular_saldo()

        if pago.reintegro_proveedor_id:
            try:
                from compraventa.models import ReintegroProveedor
                ReintegroProveedor.objects.filter(pk=pago.reintegro_proveedor_id).delete()
            except Exception:
                pass

        if pago.pago_futuro_id:
            try:
                from agenda_pagos.models import PagoFuturo
                PagoFuturo.objects.filter(pk=pago.pago_futuro_id, pagado=False).delete()
            except Exception:
                pass

        pago.delete()
        messages.success(request, "Pago eliminado y movimientos vinculados revertidos.")

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo_id)


# ==========================================================
# PAGO DE GASTOS DE CONCESIONARIO (registrar / eliminar)
# ==========================================================
@login_required
@transaction.atomic
def registrar_pago_gasto_concesionario(request):
    """Registra un pago contra un gasto de concesionario (gc_* o extra:<pk>).

    A diferencia de los gastos de ingreso, NO hay situación: estos gastos los
    paga siempre la concesionaria. Solo guardamos cuánto, cuándo, a quién y una
    observación.
    """
    if request.method != "POST":
        return redirect("vehiculos:inicio")

    vehiculo_id = request.POST.get("vehiculo_id")
    concepto_key = (request.POST.get("gasto_id") or "").strip()
    fecha_pago = request.POST.get("fecha_pago")
    monto_raw = request.POST.get("monto")
    ente = (request.POST.get("ente") or "").strip()
    observaciones = request.POST.get("observaciones") or ""

    if not vehiculo_id:
        messages.error(request, "Vehículo inválido.")
        return redirect(request.META.get("HTTP_REFERER", "vehiculos:inicio"))
    if not fecha_pago:
        messages.error(request, "Para registrar un pago es obligatorio ingresar la fecha.")
        return redirect(request.META.get("HTTP_REFERER", "vehiculos:inicio"))
    if not monto_raw:
        messages.error(request, "El monto del pago debe ser mayor a 0.")
        return redirect(request.META.get("HTTP_REFERER", "vehiculos:inicio"))

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    # Validar el concepto: campo fijo (gc_*) o un adicional (extra:<pk>)
    concepto_valido = False
    if concepto_key in GASTOS_CONC_LABELS:
        concepto_valido = True
    elif concepto_key.startswith("extra:"):
        try:
            extra_pk = int(concepto_key.split(":", 1)[1])
            concepto_valido = GastoConcesionario.objects.filter(
                pk=extra_pk, vehiculo=vehiculo
            ).exists()
        except (ValueError, IndexError):
            concepto_valido = False
    if not concepto_valido:
        messages.error(request, "Concepto de gasto de concesionario inválido.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

    try:
        monto = Decimal(str(monto_raw).replace(",", "."))
    except (ValueError, InvalidOperation):
        messages.error(request, "Monto inválido.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)
    if monto <= 0:
        messages.error(request, "El monto del pago debe ser mayor a 0.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

    PagoGastoConcesionario.objects.create(
        vehiculo=vehiculo,
        concepto=concepto_key,
        fecha_pago=fecha_pago,
        monto=monto,
        ente=ente,
        observaciones=observaciones,
    )
    messages.success(request, f"Pago de gasto de concesionario registrado: ${monto}.")
    return redirect(
        reverse("vehiculos:ficha_completa", args=[vehiculo.id]) + "#gastos-concesionario"
    )


@login_required
def eliminar_pago_gasto_concesionario(request, pago_id):
    pago = get_object_or_404(PagoGastoConcesionario, id=pago_id)
    vehiculo_id = pago.vehiculo_id
    if request.method == "POST":
        pago.delete()
        messages.success(request, "Pago de gasto de concesionario eliminado.")
    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo_id)


# ==========================================================
# QUITAR VEHÍCULO DEL STOCK (NO DELETE)
# ==========================================================
@login_required
def eliminar_vehiculo(request, vehiculo_id):
    from ventas.models import Venta
    
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method == "POST":

        # 🔒 Si tuvo ventas alguna vez → vendido
        if Venta.objects.filter(vehiculo=vehiculo).exists():
            vehiculo.estado = "vendido"
            mensaje = "El vehículo tuvo ventas y fue marcado como VENDIDO."
        else:
            vehiculo.estado = "temporal"
            mensaje = "Vehículo quitado del stock."

        vehiculo.save()

        messages.success(request, mensaje)
        return redirect("vehiculos:lista_vehiculos")

    return redirect("vehiculos:lista_vehiculos")


# ==========================================================
# BORRAR VEHÍCULO DEFINITIVAMENTE
# Solo si no tiene ninguna venta asociada (cargado por error).
# ==========================================================
@transaction.atomic
def borrar_vehiculo(request, vehiculo_id):
    from ventas.models import Venta

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method == "POST":
        ventas = Venta.objects.filter(vehiculo=vehiculo)
        # Solo bloquea si tiene una venta CONFIRMADA (venta real).
        if ventas.filter(estado="confirmada").exists():
            messages.error(
                request,
                "No se puede eliminar: el vehículo tiene una venta CONFIRMADA. "
                "Reingresalo a stock primero (se borra la venta) y después eliminalo."
            )
            return redirect("vehiculos:lista_vehiculos")

        nombre = str(vehiculo)
        try:
            # Borrar ventas viejas/no confirmadas para no dejar registros huérfanos
            ventas.delete()
            # Quitar las protecciones de Compra-Venta (operación de compra y
            # deuda del proveedor) para poder borrar un vehículo cargado por error.
            try:
                from compraventa.models import CompraVentaOperacion, DeudaProveedor
                DeudaProveedor.objects.filter(vehiculo=vehiculo).delete()
                CompraVentaOperacion.objects.filter(vehiculo=vehiculo).delete()
            except Exception:
                pass
            vehiculo.delete()
            messages.success(request, f"Vehículo {nombre} eliminado definitivamente.")
        except Exception as exc:
            messages.error(request, f"No se pudo eliminar: {exc}")

    return redirect("vehiculos:lista_vehiculos")


# ==========================================================
# AJAX – DATOS DE VEHÍCULO (RESTAURADO)
# ==========================================================
@login_required
def vehiculo_datos_ajax(request):
    """
    Devuelve datos básicos del vehículo para AJAX
    (boletos / autocompletado).
    """
    vehiculo_id = request.GET.get("vehiculo_id")

    if not vehiculo_id:
        return JsonResponse({"error": "vehiculo_id requerido"}, status=400)

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    ficha = getattr(vehiculo, "ficha", None)

    return JsonResponse({
        "id": vehiculo.id,
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "anio": vehiculo.anio,
        "dominio": vehiculo.dominio,
        "precio": str(vehiculo.precio),
        "motor": getattr(ficha, "numero_motor", "") if ficha else "",
        "chasis": getattr(ficha, "numero_chasis", "") if ficha else "",
    })


# ==========================================================
# UTIL – CONVERTIR STRING A DECIMAL SEGURO
# ==========================================================
from decimal import InvalidOperation

def to_decimal(valor):
    """
    Convierte un string a Decimal de forma segura.
    Acepta formatos comunes: 15000, 15000.00, 15.000, 15,000
    """
    if valor is None:
        return Decimal("0")

    valor = valor.strip()

    if not valor:
        return Decimal("0")

    # Quitar separadores de miles
    valor = valor.replace(".", "").replace(",", ".")

    try:
        return Decimal(valor)
    except InvalidOperation:
        return Decimal("0")


# ==========================================================
# CONFIGURACIÓN GLOBAL DE GASTOS DE INGRESO (DEFINITIVO)
# ==========================================================
@login_required
def gastos_configuracion(request):
    from vehiculos.models import ConfiguracionGastosIngreso

    # 🔒 Siempre usamos el mismo registro
    try:
        config = ConfiguracionGastosIngreso.objects.get(pk=1)
    except ConfiguracionGastosIngreso.DoesNotExist:
        config = ConfiguracionGastosIngreso.objects.create(pk=1)

    # 👇 ESTA LISTA TIENE QUE ESTAR FUERA DEL POST
    campos = [
        "gasto_f08",
        "gasto_informes",
        "gasto_patentes",
        "gasto_infracciones",
        "gasto_verificacion",
        "gasto_autopartes",
        "gasto_vtv",
        "gasto_r541",
        "gasto_firmas",
    ]

    if request.method == "POST":
        for campo in campos:
            valor = request.POST.get(campo)
            setattr(config, campo, to_decimal(valor))

        config.save()
        messages.success(request, "Gastos guardados correctamente.")

    return render(
        request,
        "vehiculos/gastos_configuracion.html",
        {"config": config},
    )


# ==========================================================
# TEST – GUARDADO CONFIGURACIÓN GASTOS
# ==========================================================
def test_guardado_gastos(request):
    from vehiculos.models import ConfiguracionGastosIngreso

    obj, _ = ConfiguracionGastosIngreso.objects.get_or_create(pk=1)
    obj.gasto_f08 = Decimal("99999")
    obj.save()
    obj.refresh_from_db()

    return HttpResponse(f"Valor guardado en DB: {obj.gasto_f08}")


# ==========================================================
# CALCULAR TOTAL DE GASTOS DE INGRESO
# ==========================================================
def calcular_total_gastos(ficha):
    """
    Recalcula y guarda el total de gastos de ingreso
    a partir de los campos individuales de la ficha.
    """
    total = Decimal("0")

    campos_gastos = [
        ficha.gasto_f08,
        ficha.gasto_informes,
        ficha.gasto_patentes,
        ficha.gasto_infracciones,
        ficha.gasto_verificacion,
        ficha.gasto_autopartes,
        ficha.gasto_vtv,
        ficha.gasto_r541,
        ficha.gasto_firmas,
    ]

    for monto in campos_gastos:
        if monto:
            total += Decimal(monto)

    ficha.total_gastos = total
    ficha.save(update_fields=["total_gastos"])


# ==========================================================
# SINCRONIZAR TURNOS Y VENCIMIENTOS CON CALENDARIO
# ==========================================================
def sincronizar_turnos_calendario(vehiculo, ficha):
    """
    Sincroniza los turnos y vencimientos del vehículo
    con la agenda/calendario.
    """
    from calendario.models import Evento

    # Borramos eventos previos del vehículo
    Evento.objects.filter(vehiculo=vehiculo).delete()

    eventos = [
        ("vtv", ficha.vtv_turno, f"Turno VTV – {vehiculo}"),
        ("autopartes", ficha.autopartes_turno, f"Turno grabado autopartes – {vehiculo}"),
        ("vtv_vencimiento", ficha.vtv_vencimiento, f"Vencimiento VTV – {vehiculo}"),
        ("verificacion_vencimiento", ficha.verificacion_vencimiento, f"Vencimiento verificación policial – {vehiculo}"),
    ]

    for tipo, fecha, titulo in eventos:
        if fecha:
            Evento.objects.create(
                vehiculo=vehiculo,
                tipo=tipo,
                fecha=fecha,
                titulo=titulo,
            )


# ==========================================================
# PDF – LISTADO DE STOCK
# ==========================================================
def stock_pdf(request):
    """
    Genera un PDF con la tabla de vehículos.
    Acepta filtros: estado, q, marca, anio_min, anio_max, precio_min, precio_max.
    Acepta columnas opcionales: col_dominio, col_anio, col_km, col_precio, col_dias, col_carpeta.
    """
    from io import BytesIO
    from datetime import date as _date

    query = request.GET.get("q", "")
    estado_filtro = request.GET.get("estado", "")
    marca_filtro = request.GET.get("marca", "").strip()
    anio_min = request.GET.get("anio_min", "")
    anio_max = request.GET.get("anio_max", "")
    precio_min = request.GET.get("precio_min", "")
    precio_max = request.GET.get("precio_max", "")

    # Columnas seleccionadas
    col_dominio = request.GET.get("col_dominio")
    col_anio = request.GET.get("col_anio")
    col_km = request.GET.get("col_km")
    col_precio = request.GET.get("col_precio")
    col_dias = request.GET.get("col_dias")
    col_carpeta = request.GET.get("col_carpeta")

    # Qué precio imprimir: "lista" (precio normal) o "reventa".
    # Si el vehículo no tiene precio de reventa cargado, se usa el de lista.
    precio_tipo = request.GET.get("precio_tipo", "lista")

    # Usuarios sin permiso de ver precios: nunca se imprime la columna Precio.
    from permisos.access import puede_ver_precio as _puede_ver_precio
    ver_precio = _puede_ver_precio(request.user)
    if not ver_precio:
        col_precio = None

    vehiculos = Vehiculo.objects.all().order_by("-id")

    if query:
        vehiculos = vehiculos.filter(
            Q(marca__icontains=query)
            | Q(modelo__icontains=query)
            | Q(dominio__icontains=query)
        )

    # Filtrar por estado:
    # - "" o "activos"  -> todo lo no vendido (stock + temporal + reventa)
    # - "stock"         -> stock + temporal (lo que está disponible)
    # - "todos"         -> absolutamente todos los vehículos
    # - cualquier otro  -> filtro exacto por ese estado
    if estado_filtro in ("", "activos"):
        vehiculos = vehiculos.exclude(estado="vendido")
    elif estado_filtro == "stock":
        vehiculos = vehiculos.filter(estado__in=["stock", "temporal"])
    elif estado_filtro == "todos":
        pass  # sin filtro de estado
    else:
        vehiculos = vehiculos.filter(estado=estado_filtro)

    if marca_filtro:
        vehiculos = vehiculos.filter(marca__icontains=marca_filtro)

    if anio_min:
        try:
            vehiculos = vehiculos.filter(anio__gte=int(anio_min))
        except ValueError:
            pass

    if anio_max:
        try:
            vehiculos = vehiculos.filter(anio__lte=int(anio_max))
        except ValueError:
            pass

    if precio_min:
        try:
            from decimal import Decimal
            vehiculos = vehiculos.filter(precio__gte=Decimal(precio_min))
        except Exception:
            pass

    if precio_max:
        try:
            from decimal import Decimal
            vehiculos = vehiculos.filter(precio__lte=Decimal(precio_max))
        except Exception:
            pass

    # Calcular días en stock
    hoy = _date.today()
    vehiculos_data = []
    for v in vehiculos:
        dias = None
        if hasattr(v, 'ficha_reporte') and v.ficha_reporte and v.ficha_reporte.fecha_compra:
            dias = (hoy - v.ficha_reporte.fecha_compra).days
        vehiculos_data.append((v, dias))

    precio_header = "Precio reventa" if precio_tipo == "reventa" else "Precio"

    # ── Construir columnas dinámicas ──────────────────────
    columnas = [("Marca / Modelo", 0.38)]  # siempre presente, más ancho

    if col_carpeta:
        columnas.append(("Carpeta", 0.10))
    if col_dominio:
        columnas.append(("Dominio", 0.12))
    if col_anio:
        columnas.append(("Año", 0.08))
    if col_km:
        columnas.append(("Kilómetros", 0.14))
    if col_precio:
        columnas.append((precio_header, 0.16))
    if col_dias:
        columnas.append(("Días", 0.10))

    # Si no eligió ninguna columna extra, mostrar todas por defecto
    if len(columnas) == 1:
        columnas = [
            ("Marca / Modelo", 0.38),
            ("Dominio", 0.12),
            ("Año", 0.08),
            ("Kilómetros", 0.14),
            ("Días", 0.10),
            ("Carpeta", 0.10),
        ]
        if ver_precio:
            columnas.insert(4, (precio_header, 0.16))

    # Ajustar anchos proporcionalmente
    total_w = sum(c[1] for c in columnas)
    columnas = [(name, w / total_w) for name, w in columnas]

    encabezado = [c[0] for c in columnas]
    filas = [encabezado]

    # Estilo para que el modelo haga wrap en celdas
    modelo_style = ParagraphStyle(
        "modelo",
        fontSize=9,
        leading=11,
        fontName="Helvetica",
    )

    for v, dias in vehiculos_data:
        modelo_txt = f"{v.marca} {v.modelo}"
        fila = [Paragraph(modelo_txt, modelo_style)]
        for col_name, _ in columnas[1:]:
            if col_name == "Carpeta":
                fila.append(v.numero_carpeta or "–")
            elif col_name == "Dominio":
                fila.append(v.dominio or "–")
            elif col_name == "Año":
                fila.append(str(v.anio))
            elif col_name == "Kilómetros":
                fila.append(f"{v.kilometros:,}".replace(",", ".") if v.kilometros else "–")
            elif col_name in ("Precio", "Precio reventa"):
                if precio_tipo == "reventa":
                    valor_precio = v.precio_reventa if v.precio_reventa is not None else v.precio
                else:
                    valor_precio = v.precio
                fila.append(f"$ {valor_precio:,.0f}".replace(",", "."))
            elif col_name == "Días":
                fila.append(f"{dias}d" if dias is not None else "–")
        filas.append(fila)

    if len(filas) == 1:
        filas.append(["Sin vehículos"] + [""] * (len(columnas) - 1))

    # ── Respuesta PDF ─────────────────────────────────────
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    title_style = ParagraphStyle(
        "title",
        fontSize=18,
        textColor=colors.HexColor("#002855"),
        alignment=1,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "subtitle",
        fontSize=10,
        alignment=1,
        textColor=colors.HexColor("#555555"),
        spaceAfter=16,
    )

    AZUL = colors.HexColor("#002855")
    AZUL_CLARO = colors.HexColor("#dce9f7")

    elements = []
    elements.append(Paragraph("AMICHETTI AUTOMOTORES", title_style))

    label_estado = {
        "stock": "En stock",
        "temporal": "No disponibles",
        "vendido": "Vendidos",
        "reventa": "En reventa",
    }.get(estado_filtro, "Todos los vehículos")

    # Subtítulo con filtros aplicados
    filtros_txt = []
    if marca_filtro:
        filtros_txt.append(f"Marca: {marca_filtro}")
    if anio_min or anio_max:
        filtros_txt.append(f"Año: {anio_min or '...'} – {anio_max or '...'}")
    if precio_min or precio_max:
        filtros_txt.append(f"Precio: ${precio_min or '...'} – ${precio_max or '...'}")
    filtros_str = (" &nbsp;|&nbsp; ".join(filtros_txt)) if filtros_txt else ""

    sub = f"Listado de vehículos – {label_estado} &nbsp;|&nbsp; {hoy.strftime('%d/%m/%Y')}"
    if precio_tipo == "reventa":
        sub += " &nbsp;|&nbsp; Precios de reventa"
    if filtros_str:
        sub += f"<br/><font size='8'>{filtros_str}</font>"

    elements.append(Paragraph(sub, subtitle_style))

    # ── Tabla ─────────────────────────────────────────────
    col_widths = [doc.width * w for _, w in columnas]

    tabla = Table(filas, colWidths=col_widths, repeatRows=1)

    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO]),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    elements.append(tabla)

    # ── Pie ───────────────────────────────────────────────
    elements.append(Spacer(1, 16))
    pie_style = ParagraphStyle(
        "pie",
        fontSize=8,
        textColor=colors.HexColor("#888888"),
        alignment=1,
    )
    elements.append(
        Paragraph(
            f"Total de vehículos: {len(filas) - 1}",
            pie_style,
        )
    )

    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="stock_vehiculos.pdf"'
    return response


# ==========================================================
# FICHA VEHICULAR PDF
# ==========================================================
def ficha_vehicular_pdf(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha = vehiculo.ficha

    # ?seccion= permite descargar solo una parte de la ficha.
    # Valores aceptados: 'completa' (default), 'documentacion', 'gastos',
    # 'tecnica'. Se mantiene 'completa' como comportamiento histórico.
    seccion_param = (request.GET.get("seccion") or "completa").lower()
    _validos = {"completa", "documentacion", "gastos", "tecnica"}
    if seccion_param not in _validos:
        seccion_param = "completa"

    def incluir(nombre):
        return seccion_param == "completa" or seccion_param == nombre

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="ficha_{seccion_param}_{vehiculo.id}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    # ==================================================
    # ESTILOS – IDENTIDAD AMICHETTI
    # ==================================================
    title_style = ParagraphStyle(
        "title",
        fontSize=18,
        textColor=colors.HexColor("#002855"),
        alignment=1,
        fontName="Helvetica-Bold",
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "subtitle",
        fontSize=11,
        alignment=1,
        spaceAfter=16
    )

    section_title_style = ParagraphStyle(
        "section",
        fontSize=11,
        textColor=colors.white,
        backColor=colors.HexColor("#002855"),
        fontName="Helvetica-Bold",
        leftIndent=6,
        spaceBefore=12,
        spaceAfter=6
    )

    # ==================================================
    # HEADER
    # ==================================================
    elements.append(Paragraph("AMICHETTI AUTOMOTORES", title_style))
    elements.append(Paragraph("Ficha Vehicular", subtitle_style))

    # ==================================================
    # FUNCIÓN PARA SECCIONES
    # ==================================================
    def seccion(titulo, filas):
        elements.append(Paragraph(titulo, section_title_style))

        table = Table(
            filas,
            colWidths=[doc.width * 0.35, doc.width * 0.65]
        )

        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        elements.append(table)

    # ==================================================
    # DATOS DEL VEHÍCULO (siempre se imprimen como cabecera de contexto)
    # ==================================================
    if incluir("documentacion") or incluir("tecnica") or seccion_param == "completa" or seccion_param == "gastos":
        seccion("Datos del vehículo", [
            ["Marca", vehiculo.marca],
            ["Modelo", vehiculo.modelo],
            ["Dominio", vehiculo.dominio or "-"],
            ["Año", vehiculo.anio],
            ["Kilometraje", vehiculo.kilometros or "-"],
            ["Precio", f"$ {vehiculo.precio}"],
            ["Número de carpeta", vehiculo.numero_carpeta or "-"],
        ])

    # ==================================================
    # IDENTIFICACIÓN
    # ==================================================
    if seccion_param == "completa" or seccion_param == "documentacion":
        seccion("Identificación", [
            ["Número de motor", ficha.numero_motor or "-"],
            ["Número de chasis", ficha.numero_chasis or "-"],
            ["Fecha inscripción inicial", ficha.fecha_inscripcion_inicial or "-"],
            ["Color", ficha.color or "-"],
            ["Combustible", ficha.combustible or "-"],
            ["Transmisión", ficha.transmision or "-"],
        ])

    # ==================================================
    # DOCUMENTACIÓN
    # ==================================================
    if seccion_param == "completa" or seccion_param == "documentacion":
        seccion("Documentación", [
            [
                "Patentes",
                f"{ficha.patentes_estado or '-'}"
                + (f" – $ {ficha.patentes_monto}" if ficha.patentes_monto else "")
            ],
            ["Formulario 08", ficha.get_f08_estado_display() if ficha.f08_estado else "-"],
            ["Cédula", ficha.cedula_estado or "-"],
            ["Informe", ficha.get_informe_display() if ficha.informe else "-"],
            ["Radicación anterior", ficha.radicacion_anterior or "-"],
            [
                "Verificación policial",
                f"{ficha.verificacion_estado or '-'}"
                + (f" – {ficha.verificacion_vencimiento}" if ficha.verificacion_vencimiento else "")
            ],
            ["Grabado autopartes", ficha.autopartes_estado or "-"],
            [
                "VTV",
                f"{ficha.vtv_estado or '-'}"
                + (f" – {ficha.vtv_vencimiento}" if ficha.vtv_vencimiento else "")
            ],
        ])

    # ==================================================
    # GASTOS DE INGRESO
    # ==================================================
    if seccion_param == "completa" or seccion_param == "gastos":
        seccion("Gastos de ingreso", [
            ["Formulario 08", f"$ {ficha.gasto_f08 or 0}"],
            ["Informes", f"$ {ficha.gasto_informes or 0}"],
            ["Patentes", f"$ {ficha.gasto_patentes or 0}"],
            ["Infracciones", f"$ {ficha.gasto_infracciones or 0}"],
            ["Verificación", f"$ {ficha.gasto_verificacion or 0}"],
            ["Autopartes", f"$ {ficha.gasto_autopartes or 0}"],
            ["VTV", f"$ {ficha.gasto_vtv or 0}"],
            ["R-541", f"$ {ficha.gasto_r541 or 0}"],
            ["Firmas", f"$ {ficha.gasto_firmas or 0}"],
            ["TOTAL", f"$ {ficha.total_gastos or 0}"],
        ])

        # Gastos del concesionario (gc_*)
        seccion("Gastos del concesionario", [
            ["Service",              f"$ {ficha.gc_service or 0}"],
            ["Mecánica",             f"$ {ficha.gc_mecanica or 0}"],
            ["Chapa y pintura",      f"$ {ficha.gc_chapa_pintura or 0}"],
            ["Tapizado",             f"$ {ficha.gc_tapizado or 0}"],
            ["Neumáticos",           f"$ {ficha.gc_neumaticos or 0}"],
            ["Vidrios",              f"$ {ficha.gc_vidrios or 0}"],
            ["Cerrajería",           f"$ {ficha.gc_cerrajeria or 0}"],
            ["Lavado / Pulido",      f"$ {ficha.gc_lavado or 0}"],
            ["GNC",                  f"$ {ficha.gc_gnc or 0}"],
            ["Grabado autopartes",   f"$ {ficha.gc_grabado_autopartes or 0}"],
            ["VTV",                  f"$ {ficha.gc_vtv or 0}"],
            ["Verificación policial", f"$ {ficha.gc_verificacion or 0}"],
            ["Patentes",             f"$ {ficha.gc_patentes or 0}"],
            ["Otros",                f"$ {ficha.gc_otros or 0}"],
        ])

    # ==================================================
    # OBSERVACIONES Y DATOS ADICIONALES
    # ==================================================
    if seccion_param == "completa" or seccion_param == "documentacion":
        seccion("Observaciones", [
            ["Observaciones", ficha.observaciones or "Sin observaciones"],
            ["Segunda llave", f"{ficha.duplicado_llave_estado or '-'} - {ficha.duplicado_llave_obs or '-'}"],
            ["Código de llave", f"{ficha.codigo_llave_estado or '-'} - {ficha.codigo_llave_obs or '-'}"],
            ["Oblea GNC", f"{ficha.oblea_gnc_estado or '-'} - {ficha.oblea_gnc_obs or '-'}"],
            ["Código de radio", f"{ficha.codigo_radio_estado or '-'} - {ficha.codigo_radio_obs or '-'}"],
            ["Manuales", f"{ficha.manuales_estado or '-'} - {ficha.manuales_obs or '-'}"],
        ])

    # ==================================================
    # FICHA TÉCNICA (mantenimiento + cubiertas + sistemas + granizo)
    # ==================================================
    if seccion_param == "completa" or seccion_param == "tecnica":
        ftec = getattr(vehiculo, "ficha_tecnica", None)
        if ftec is not None:
            def _disp(field):
                """Devuelve get_X_display() si existe, sino el valor crudo."""
                getter = getattr(ftec, f"get_{field}_display", None)
                if callable(getter):
                    val = getter()
                    return val if val else "-"
                val = getattr(ftec, field, None)
                return val if val not in (None, "") else "-"

            seccion("Mantenimiento", [
                ["Último service", f"{ftec.ultimo_service_fecha or '-'} / {ftec.ultimo_service_km or '-'} km"],
                ["Cambio de aceite", f"{ftec.ultimo_cambio_aceite_fecha or '-'} / {ftec.ultimo_cambio_aceite_km or '-'} km"],
                ["Cambio de correa", f"{ftec.ultimo_cambio_correa_fecha or '-'} / {ftec.ultimo_cambio_correa_km or '-'} km"],
            ])

            seccion("Historia y estado", [
                ["¿Repintado?", _disp("repintado")],
                ["Partes repintadas", ftec.partes_repintadas or "-"],
                ["¿Tuvo choque?", _disp("chocado")],
                ["Detalles del choque", ftec.detalles_choque or "-"],
                ["Detalles (rayones, golpes)", ftec.detalles_estado or "-"],
                ["¿Algo no funciona?", ftec.no_funciona or "-"],
            ])

            seccion("Cubiertas", [
                ["Delantera izq.", _disp("cubierta_di")],
                ["Delantera der.", _disp("cubierta_dd")],
                ["Trasera izq.",   _disp("cubierta_ti")],
                ["Trasera der.",   _disp("cubierta_td")],
                ["Rueda de auxilio", _disp("cubierta_auxilio")],
                ["Observaciones",  ftec.cubiertas_obs or "-"],
            ])

            seccion("Estado de sistemas", [
                ["Motor",              _disp("estado_motor")],
                ["Pérdida de fluidos", _disp("perdida_fluidos")],
                ["Detalle fluidos",    ftec.perdida_fluidos_obs or "-"],
                ["Suspensión",         _disp("estado_suspension")],
                ["Sistema de frenos",  _disp("estado_frenos")],
                ["Sistema eléctrico",  _disp("estado_electrico")],
                ["Detalle eléctrico",  ftec.fallas_electrico_obs or "-"],
                ["Faros y ópticas",    _disp("estado_faros_opticas")],
                ["Tapizados",          _disp("estado_tapizados")],
                ["Desgaste volante",   _disp("estado_volante")],
                ["Vidrios",            _disp("estado_vidrios")],
                ["Calefacción",        _disp("estado_calefaccion")],
                ["Aire acondicionado", _disp("estado_aire")],
            ])

            seccion("Granizo", [
                ["Nivel", _disp("granizo_estado")],
                ["Detalles", ftec.granizo_obs or "-"],
            ])

            if ftec.observaciones_tecnicas:
                seccion("Observaciones técnicas", [
                    ["", ftec.observaciones_tecnicas],
                ])

    # ==================================================
    # GENERAR PDF
    # ==================================================
    doc.build(elements)
    return response


@transaction.atomic
def guardar_ficha_parcial(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    if request.method == "POST":
        # Precio de reventa: es un campo del Vehiculo (no de la ficha), editable
        # desde la pestaña Documentación. Lo guardamos aparte.
        if "precio_reventa" in request.POST:
            pr_raw = (request.POST.get("precio_reventa") or "").strip().replace("$", "").replace(" ", "")
            if "," in pr_raw:
                pr_raw = pr_raw.replace(".", "").replace(",", ".")
            try:
                vehiculo.precio_reventa = Decimal(pr_raw) if pr_raw else None
                vehiculo.save(update_fields=["precio_reventa"])
            except Exception:
                pass

        # Solo actualizar los campos que vienen en el POST,
        # sin tocar los demás (evita borrar datos de otras secciones)
        campos_enviados = [
            campo for campo in FichaVehicularForm.Meta.fields
            if campo in request.POST
        ]

        if campos_enviados:
            # Crear form dinámico solo con los campos enviados
            class FichaParcialForm(FichaVehicularForm):
                class Meta(FichaVehicularForm.Meta):
                    fields = campos_enviados

            ficha_form = FichaParcialForm(request.POST, instance=ficha)

            # Valores anteriores para decidir si re-sincronizar gasto_patentes.
            _patentes_monto_old = getattr(ficha, "patentes_monto", None) or Decimal("0")
            _gasto_pat_old = getattr(ficha, "gasto_patentes", None) or Decimal("0")

            if ficha_form.is_valid():
                ficha_form.save()

                # Vincular el "Monto adeudado" de patentes con el gasto de
                # ingreso de Patentes: si el auto adeuda patentes, esa deuda
                # es un gasto de ingreso que paga la concesionaria.
                # ⚠️ SOLO sincronizamos cuando el monto de patentes CAMBIÓ en
                # este guardado, o cuando gasto_patentes estaba vacío. Así no
                # pisamos un gasto_patentes ajustado a mano en cada guardado.
                if "patentes_adeuda" in campos_enviados and ficha.patentes_adeuda == "si":
                    monto_nuevo = ficha.patentes_monto or Decimal("0")
                    if monto_nuevo != _patentes_monto_old or _gasto_pat_old == 0:
                        ficha.gasto_patentes = monto_nuevo
                        ficha.save(update_fields=["gasto_patentes"])

                sincronizar_turnos_calendario(vehiculo, ficha)
                from vehiculos.services import recalcular_cuentas_vinculadas
                recalcular_cuentas_vinculadas(vehiculo)
                messages.success(request, "Cambios guardados correctamente.")
            else:
                messages.error(request, "Error al guardar los cambios.")
        else:
            messages.error(request, "No se recibieron campos para guardar.")

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)


# ==========================================================
# MANTENIMIENTOS
# ==========================================================
@csrf_exempt
def agregar_mantenimiento(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        fecha = request.POST.get("fecha", "").strip()
        observacion = request.POST.get("observacion", "").strip()

        if nombre and fecha:
            mant = Mantenimiento.objects.create(
                vehiculo=vehiculo,
                nombre=nombre,
                fecha=fecha,
                observacion=observacion,
            )
            return JsonResponse({
                "ok": True,
                "id": mant.id,
                "nombre": mant.nombre,
                "fecha": mant.fecha.strftime("%d/%m/%Y"),
                "observacion": mant.observacion or "",
            })

    return JsonResponse({"ok": False}, status=400)


@csrf_exempt
def eliminar_mantenimiento(request, pk):
    mant = get_object_or_404(Mantenimiento, pk=pk)
    mant.delete()
    return JsonResponse({"ok": True})