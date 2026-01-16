print(">>> CARGANDO views.py")

from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.db.models import Q, Sum
from django.db import transaction
from django.contrib.auth.decorators import login_required

from .models import (
    Vehiculo,
    FichaVehicular,
    PagoGastoIngreso,
    ConfiguracionGastosIngreso
)

from .forms import VehiculoBasicoForm, VehiculoForm, FichaVehicularForm

# ==========================================================
# ACCESO ÚNICO A CONFIGURACIÓN GLOBAL DE GASTOS (ÚNICO VÁLIDO)
# ==========================================================
def get_configuracion_gastos():
    return ConfiguracionGastosIngreso.objects.get(pk=1)
def lista_vehiculos(request):
    query = request.GET.get("q", "")
    vehiculos = Vehiculo.objects.exclude(estado="vendido").order_by("-id")

    if query:
        vehiculos = vehiculos.filter(
            Q(marca__icontains=query)
            | Q(modelo__icontains=query)
            | Q(dominio__icontains=query)
        )

    return render(
        request,
        "vehiculos/lista_vehiculos.html",
        {"vehiculos": vehiculos, "query": query},
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
                    "gasto_verificacion": config.gasto_verificacion,
                    "gasto_autopartes": config.gasto_autopartes,
                    "gasto_vtv": config.gasto_vtv,
                    "gasto_r541": config.gasto_r541,
                    "gasto_firmas": config.gasto_firmas,
                }
            )

            messages.success(request, "Vehículo agregado correctamente.")
            return redirect("vehiculos:lista_vehiculos")

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

        vehiculo.estado = nuevo_estado
        vehiculo.save(update_fields=["estado"])

        from gestoria.models import Gestoria
        Gestoria.objects.filter(vehiculo=vehiculo).delete()

        messages.success(
            request,
            "Estado actualizado. La unidad fue retirada de Gestoría."
        )

    return redirect("vehiculos:lista_vehiculos")
# ==========================================================
# MODAL FICHA VEHICULAR (AJAX) – DEFINITIVA
# ==========================================================
def ficha_vehicular_ajax(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    vehiculo_form = VehiculoForm(instance=vehiculo)
    ficha_form = FichaVehicularForm(instance=ficha)

    CONCEPTOS = {
        "f08": "Formulario 08",
        "informes": "Informes",
        "patentes": "Patentes",
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

    html = render_to_string(
        "vehiculos/modal_ficha_vehicular.html",
        {
            "vehiculo": vehiculo,
            "ficha": ficha,
            "vehiculo_form": vehiculo_form,
            "ficha_form": ficha_form,
            "gastos_ingreso": gastos_ingreso,
            "total_pendiente": total_pendiente,
        },
        request=request,
    )

    return JsonResponse({"html": html})

# ==========================================================
# GUARDAR FICHA VEHICULAR (FINAL – LIMPIO Y CORRECTO)
# ==========================================================
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

@transaction.atomic
def guardar_ficha_vehicular(request, vehiculo_id):
     
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    if request.method == "POST":

        vehiculo_form = VehiculoForm(request.POST, instance=vehiculo)
        ficha_form = FichaVehicularForm(request.POST, instance=ficha)

        if vehiculo_form.is_valid() and ficha_form.is_valid():

            # ===============================
            # GUARDAR VEHÍCULO
            # ===============================
            vehiculo_form.save()

            # ===============================
            # GUARDAR FICHA (EL FORM ES LA FUENTE)
            # ===============================
            ficha = ficha_form.save(commit=False)

            # ===============================
            # CAMPOS MANUALES (NO ESTÁN EN EL FORM)
            # ===============================
            ficha.titulo_estado = request.POST.get("titulo_estado") or ficha.titulo_estado
            ficha.titulo_obs = request.POST.get("titulo_obs") or ficha.titulo_obs
            ficha.cedula_check_estado = request.POST.get("cedula_check_estado") or ficha.cedula_check_estado
            ficha.cedula_check_obs = request.POST.get("cedula_check_obs") or ficha.cedula_check_obs
            ficha.prenda_estado = request.POST.get("prenda_estado") or ficha.prenda_estado
            ficha.prenda_obs = request.POST.get("prenda_obs") or ficha.prenda_obs

            ficha.save()

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

    CONCEPTOS = {
        "f08": "Formulario 08",
        "informes": "Informes",
        "patentes": "Patentes",
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

    ficha.total_gastos = total_pendiente
    ficha.save(update_fields=["total_gastos"])

    return render(
        request,
        "vehiculos/ficha_completa.html",
        {
            "vehiculo": vehiculo,
            "ficha": ficha,
            "gastos_ingreso": gastos_ingreso,
            "total_pendiente": total_pendiente,
        },
    )


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
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

from .models import Vehiculo, PagoGastoIngreso
from cuentas.models import MovimientoCuenta


@csrf_exempt              # 🔴 SOLO PARA PROBAR (DESPUÉS SE SACA)
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
    saldo_actual = ficha.saldo_por_concepto(CONCEPTOS[concepto_key])
    monto = Decimal(monto_raw)

    if monto > saldo_actual:
        monto = saldo_actual

    if monto <= 0:
        messages.warning(request, "El gasto ya está totalmente pagado.")
        return redirect("vehiculos:ficha_completa", vehiculo_id=vehiculo.id)

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
    if vehiculo.venta and hasattr(vehiculo.venta, "cuenta_corriente"):
        cuenta = vehiculo.venta.cuenta_corriente

    if cuenta:
        MovimientoCuenta.objects.create(
            cuenta=cuenta,
            vehiculo=vehiculo,
            descripcion=CONCEPTOS[concepto_key],
            tipo="haber",          # 👈 RESTA DEUDA
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
# ELIMINAR VEHÍCULO (SIN DELETE FÍSICO)
# ==========================================================
def eliminar_vehiculo(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    from ventas.models import Venta

    # Si el vehículo tiene historial de ventas, no se permite eliminar
    if Venta.objects.filter(
        vehiculo=vehiculo,
        estado__in=["pendiente", "confirmada", "revertida"]
    ).exists():
        messages.error(
            request,
            "No se puede eliminar el vehículo porque tiene historial de ventas asociado."
        )
        return redirect("vehiculos:lista_vehiculos")

    if request.method == "POST":
        vehiculo.estado = "anulado"
        vehiculo.save(update_fields=["estado"])

        messages.success(
            request,
            "Vehículo marcado como ANULADO correctamente."
        )

    return redirect("vehiculos:lista_vehiculos")
# ==========================================================
# AJAX – DATOS DE VEHÍCULO (RESTAURADO)
# ==========================================================
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

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

    return JsonResponse({
        "id": vehiculo.id,
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "dominio": vehiculo.dominio,
        "precio": str(vehiculo.precio),
    })
# ==========================================================
# UTIL – CONVERTIR STRING A DECIMAL SEGURO
# ==========================================================
from decimal import Decimal, InvalidOperation

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
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib import messages

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
from django.http import HttpResponse
from decimal import Decimal

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
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404

def ficha_vehicular_pdf(request, vehiculo_id):
    """
    Genera PDF de la ficha vehicular.
    ⚠️ Requiere WeasyPrint + dependencias del sistema.
    """
    from weasyprint import HTML  # import local

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha = vehiculo.ficha

    html_string = render_to_string(
        "vehiculos/ficha_vehicular_pdf.html",
        {
            "vehiculo": vehiculo,
            "ficha": ficha,
        }
    )

    pdf = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="ficha_vehiculo_{vehiculo.id}.pdf"'
    )

    return response