from decimal import Decimal
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.db.models import Q, Sum
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
# ACCESO ÚNICO A CONFIGURACIÓN GLOBAL DE GASTOS (ÚNICO VÁLIDO)
# ==========================================================
def get_configuracion_gastos():
    config, _ = ConfiguracionGastosIngreso.objects.get_or_create(pk=1)
    return config


# ==========================================================
# LISTA DE VEHÍCULOS CON FILTROS Y DÍAS EN STOCK
# ==========================================================
def lista_vehiculos(request):
    query = request.GET.get("q", "")
    estado_filtro = request.GET.get("estado", "")
    
    vehiculos = Vehiculo.objects.all().select_related('ficha').order_by("-id")

    # Filtro por búsqueda
    if query:
        vehiculos = vehiculos.filter(
            Q(marca__icontains=query)
            | Q(modelo__icontains=query)
            | Q(dominio__icontains=query)
        )
    
    # Filtro por estado
    if estado_filtro:
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
    total_stock = Vehiculo.objects.filter(estado='stock').count()
    total_temporal = Vehiculo.objects.filter(estado='temporal').count()
    total_vendido = Vehiculo.objects.filter(estado='vendido').count()
    total_reventa = Vehiculo.objects.filter(estado='reventa').count()

    return render(
        request,
        "vehiculos/lista_vehiculos.html",
        {
            "vehiculos_con_dias": vehiculos_con_dias,
            "query": query,
            "estado_filtro": estado_filtro,
            "total_stock": total_stock,
            "total_temporal": total_temporal,
            "total_vendido": total_vendido,
            "total_reventa": total_reventa,
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


@transaction.atomic
def cambiar_estado_vehiculo(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")

        # ===============================
        # MARCAR COMO VENDIDO
        # ===============================
        if nuevo_estado == "vendido":
            from ventas.models import Venta
            from gestoria.models import Gestoria

            venta, creada = Venta.objects.get_or_create(
                vehiculo=vehiculo,
                defaults={
                    "estado": "confirmada",
                    "precio_venta": vehiculo.precio,
                }
            )

            if not creada and venta.estado != "confirmada":
                venta.estado = "confirmada"
                venta.save(update_fields=["estado"])

            vehiculo.estado = "vendido"
            vehiculo.save(update_fields=["estado"])

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
        # REVERTIR VENTA / VOLVER A STOCK
        # ===============================
        vehiculo.estado = nuevo_estado
        vehiculo.save(update_fields=["estado"])

        # ELIMINAR LA VENTA SI EXISTE
        if hasattr(vehiculo, "venta"):
            venta = vehiculo.venta
            # Desvincular cuenta corriente (no se borra, queda el historial)
            from cuentas.models import CuentaCorriente
            CuentaCorriente.objects.filter(venta=venta).update(
                venta=None, estado="cerrada"
            )
            venta.delete()

        from gestoria.models import Gestoria
        Gestoria.objects.filter(vehiculo=vehiculo).delete()

        messages.success(
            request,
            "Estado actualizado. La unidad volvió a stock y la venta fue eliminada."
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
                concepto=key
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
        ficha_form = FichaVehicularForm(request.POST, instance=ficha)
        ficha_tecnica_form = FichaTecnicaForm(request.POST, instance=ficha_tec)

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

            ficha = ficha_form.save(commit=False)

            # Restaurar gastos que el form pudo haber borrado
            for campo, valor in gastos_preservar.items():
                if getattr(ficha, campo, None) is None and valor is not None:
                    setattr(ficha, campo, valor)

            # ===============================
            # CAMPOS MANUALES (NO ESTÁN EN EL FORM)
            # ===============================
            ficha.titulo_estado = request.POST.get("titulo_estado") or ficha.titulo_estado
            ficha.titulo_obs = request.POST.get("titulo_obs") or ficha.titulo_obs
            ficha.cedula_check_estado = request.POST.get("cedula_check_estado") or ficha.cedula_check_estado
            ficha.cedula_check_obs = request.POST.get("cedula_check_obs") or ficha.cedula_check_obs
            ficha.prenda_estado = request.POST.get("prenda_estado") or ficha.prenda_estado
            ficha.prenda_obs = request.POST.get("prenda_obs") or ficha.prenda_obs

            # Gastos concesionario
            campos_gc = [
                "gc_service", "gc_mecanica", "gc_chapa_pintura", "gc_tapizado",
                "gc_neumaticos", "gc_vidrios", "gc_cerrajeria", "gc_lavado",
                "gc_gnc", "gc_grabado_autopartes", "gc_vtv", "gc_verificacion", "gc_patentes", "gc_otros",
            ]
            for campo in campos_gc:
                valor = request.POST.get(campo, "").replace(",", ".")
                if valor:
                    try:
                        setattr(ficha, campo, Decimal(valor))
                    except Exception:
                        pass

            ficha.save()

            # ===============================
            # GUARDAR FICHA TÉCNICA
            # ===============================
            if ficha_tecnica_form.is_valid():
                ficha_tecnica_form.save()

            # ===============================
            # POST-GUARDADO
            # ===============================
            calcular_total_gastos(ficha)
            sincronizar_turnos_calendario(vehiculo, ficha)

            messages.success(request, "Cambios guardados correctamente.")
            return redirect(
                "vehiculos:ficha_completa",
                vehiculo_id=vehiculo.id
            )

        # ❌ Formularios inválidos
        messages.error(request, "Error al guardar los cambios.")
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

        total_pagado = (
            PagoGastoIngreso.objects.filter(
                vehiculo=vehiculo,
                concepto=key
            ).aggregate(total=Sum("monto"))["total"]
            or Decimal("0")
        )

        saldo = monto - Decimal(total_pagado)

        # 🆕 OBTENER HISTORIAL DE PAGOS DE ESTE CONCEPTO
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
            "saldo": saldo,
            "pagos": pagos,
            "esta_pagado": esta_pagado,
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
        for campo in campos_gc:
            valor = request.POST.get(campo, "0").replace(",", ".")
            try:
                setattr(ficha, campo, Decimal(valor) if valor else Decimal("0"))
            except Exception:
                setattr(ficha, campo, Decimal("0"))

        ficha.save(update_fields=campos_gc)
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

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)


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

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo_id)


# ==========================================================
# AGREGAR GASTO INGRESO (CUENTA CORRIENTE)
# ==========================================================
@transaction.atomic
def agregar_gasto_ingreso(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    cuenta = vehiculo.venta.cuenta_corriente

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
# REGISTRAR PAGO DE GASTO DE INGRESO (DEFINITIVO)
# ==========================================================
from cuentas.models import MovimientoCuenta


@csrf_exempt
@transaction.atomic
def registrar_pago_gasto(request):

    print(">>> ENTRÓ A registrar_pago_gasto")
    print(">>> METHOD:", request.method)
    print(">>> POST:", dict(request.POST))

    if request.method != "POST":
        return redirect("vehiculos:inicio")

    vehiculo_id = request.POST.get("vehiculo_id")
    concepto_key = (request.POST.get("gasto_id") or "").strip()
    fecha_pago = request.POST.get("fecha_pago")
    monto_raw = request.POST.get("monto")
    observaciones = request.POST.get("observaciones")

    print(">>> DATOS RECIBIDOS:", vehiculo_id, concepto_key, fecha_pago, monto_raw)

    # ===============================
    # VALIDACIONES BÁSICAS
    # ===============================
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

    # ===============================
    # CONCEPTOS CANÓNICOS
    # ===============================
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

    if concepto_key not in CONCEPTOS:
        messages.error(request, "Concepto de gasto inválido.")
        return redirect(request.META.get("HTTP_REFERER"))

    # ===============================
    # CALCULAR SALDO REAL
    # ===============================
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

    monto_gasto = mapa_gastos.get(concepto_key) or Decimal("0")

    total_pagado = (
        PagoGastoIngreso.objects.filter(
            vehiculo=vehiculo,
            concepto=concepto_key
        ).aggregate(total=Sum("monto"))["total"]
        or Decimal("0")
    )

    saldo_actual = Decimal(monto_gasto) - Decimal(total_pagado)
    monto = Decimal(monto_raw)

    # ===============================
    # REGISTRAR PAGO DE GASTO
    # ===============================
    PagoGastoIngreso.objects.create(
        vehiculo=vehiculo,
        concepto=concepto_key,
        fecha_pago=fecha_pago,
        monto=monto,
        observaciones=observaciones,
    )

    # ===============================
    # IMPACTAR CUENTA CORRIENTE (HABER – PERMUTA)
    # ===============================
    cuenta = None
    if hasattr(vehiculo, "venta") and vehiculo.venta:
        if hasattr(vehiculo.venta, "cuenta_corriente"):
            cuenta = vehiculo.venta.cuenta_corriente
    if cuenta:
        MovimientoCuenta.objects.create(
            cuenta=cuenta,
            vehiculo=vehiculo,
            descripcion=CONCEPTOS[concepto_key],
            tipo="haber",
            monto=monto,
            origen="permuta"
        )

        cuenta.recalcular_saldo()

    messages.success(
        request,
        f"Pago registrado. {CONCEPTOS[concepto_key]}: ${monto}"
    )

    return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)


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
    estado_filtro = request.GET.get("estado", "stock")
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

    vehiculos = Vehiculo.objects.all().order_by("-id")

    if query:
        vehiculos = vehiculos.filter(
            Q(marca__icontains=query)
            | Q(modelo__icontains=query)
            | Q(dominio__icontains=query)
        )

    # Siempre excluir vendidos del PDF del listado
    if estado_filtro and estado_filtro != "vendido":
        vehiculos = vehiculos.filter(estado=estado_filtro)
    else:
        vehiculos = vehiculos.exclude(estado="vendido")

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
        columnas.append(("Precio", 0.16))
    if col_dias:
        columnas.append(("Días", 0.10))

    # Si no eligió ninguna columna extra, mostrar todas por defecto
    if len(columnas) == 1:
        columnas = [
            ("Marca / Modelo", 0.38),
            ("Dominio", 0.12),
            ("Año", 0.08),
            ("Kilómetros", 0.14),
            ("Precio", 0.16),
            ("Días", 0.10),
            ("Carpeta", 0.10),
        ]

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
            elif col_name == "Precio":
                fila.append(f"$ {v.precio:,.0f}".replace(",", "."))
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
        "temporal": "Temporalmente no disponibles",
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

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="ficha_vehicular_{vehiculo.id}.pdf"'
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
    # DATOS DEL VEHÍCULO
    # ==================================================
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
    seccion("Documentación", [
        [
            "Patentes",
            f"{ficha.patentes_estado or '-'}"
            + (f" – $ {ficha.patentes_monto}" if ficha.patentes_monto else "")
        ],
        ["Formulario 08", ficha.f08_estado or "-"],
        ["Cédula", ficha.cedula_estado or "-"],
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

    # ==================================================
    # OBSERVACIONES Y DATOS ADICIONALES
    # ==================================================
    seccion("Observaciones", [
        ["Observaciones", ficha.observaciones or "Sin observaciones"],
        ["Segunda llave", f"{ficha.duplicado_llave_estado or '-'} - {ficha.duplicado_llave_obs or '-'}"],
        ["Código de llave", f"{ficha.codigo_llave_estado or '-'} - {ficha.codigo_llave_obs or '-'}"],
        ["Oblea GNC", f"{ficha.oblea_gnc_estado or '-'} - {ficha.oblea_gnc_obs or '-'}"],
        ["Código de radio", f"{ficha.codigo_radio_estado or '-'} - {ficha.codigo_radio_obs or '-'}"],
        ["Manuales", f"{ficha.manuales_estado or '-'} - {ficha.manuales_obs or '-'}"],
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
        ficha_form = FichaVehicularForm(request.POST, instance=ficha)

        if ficha_form.is_valid():
            ficha_form.save()
            sincronizar_turnos_calendario(vehiculo, ficha)
            messages.success(request, "Cambios guardados correctamente.")
        else:
            messages.error(request, "Error al guardar los cambios.")

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