from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.db.models import Q, Sum
from django.db import transaction
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ✅ SOLO PARA PDF VISUAL
from weasyprint import HTML, CSS

from .models import Vehiculo, FichaVehicular, PagoGastoIngreso
from .forms import VehiculoBasicoForm, VehiculoForm, FichaVehicularForm

# ===============================
# 🔹 AGREGADO PARA CALENDARIO
# ===============================
from calendario.models import Evento


# ==========================================================
# LISTA / STOCK DE VEHÍCULOS
# ==========================================================
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
        {
            "vehiculos": vehiculos,
            "query": query,
        },
    )


# ==========================================================
# LISTADO DE VEHÍCULOS VENDIDOS
# ==========================================================
def lista_vehiculos_vendidos(request):
    vehiculos = Vehiculo.objects.filter(estado="vendido").order_by("-id")

    return render(
        request,
        "vehiculos/lista_vehiculos_vendidos.html",
        {
            "vehiculos": vehiculos,
        },
    )


# ==========================================================
# CAMBIAR ESTADO DE VEHÍCULO
# ==========================================================
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

    return redirect("vehiculos:lista_vehiculos")


# ==========================================================
# AGREGAR VEHÍCULO BÁSICO
# ==========================================================
def agregar_vehiculo(request):
    if request.method == "POST":
        form = VehiculoBasicoForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Vehículo agregado correctamente.")
            return redirect("vehiculos:lista_vehiculos")
        else:
            messages.error(
                request,
                "No se pudo guardar el vehículo. Revisá los datos ingresados."
            )
    else:
        form = VehiculoBasicoForm()

    return render(
        request,
        "vehiculos/agregar_vehiculo.html",
        {
            "form": form,
        },
    )


# ==========================================================
# MODAL FICHA VEHICULAR (AJAX)
# ==========================================================
def ficha_vehicular_ajax(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    vehiculo_form = VehiculoForm(instance=vehiculo)
    ficha_form = FichaVehicularForm(instance=ficha)

    mapa_gastos = {
        "Formulario 08": ficha.gasto_f08,
        "Informes": ficha.gasto_informes,
        "Patentes": ficha.gasto_patentes,
        "Verificación": ficha.gasto_verificacion,
        "Autopartes": ficha.gasto_autopartes,
        "VTV": ficha.gasto_vtv,
        "R541": ficha.gasto_r541,
        "Firmas": ficha.gasto_firmas,
    }

    gastos_ingreso = []
    for concepto, monto in mapa_gastos.items():
        if not monto or monto <= 0:
            continue

        total_pagado = (
            PagoGastoIngreso.objects.filter(
                vehiculo=vehiculo,
                concepto=concepto
            ).aggregate(total=Sum("monto"))["total"]
            or Decimal("0")
        )

        gastos_ingreso.append({
            "concepto": concepto,
            "monto": monto,
            "total_pagado": total_pagado,
            "saldo": Decimal(monto) - total_pagado,
        })

    total_pendiente = sum(g["saldo"] for g in gastos_ingreso)

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
from django.contrib.auth.decorators import login_required

@transaction.atomic
def guardar_ficha_vehicular(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    if request.method == "POST":
        vehiculo_form = VehiculoForm(request.POST, instance=vehiculo)
        ficha_form = FichaVehicularForm(request.POST, instance=ficha)

        if vehiculo_form.is_valid() and ficha_form.is_valid():
            vehiculo_form.save()

            ficha = ficha_form.save(commit=False)
            ficha.vehiculo = vehiculo
            ficha.save()

            calcular_total_gastos(ficha)
            sincronizar_turnos_calendario(vehiculo, ficha)

            messages.success(request, "Cambios guardados correctamente.")
            return redirect("vehiculos:lista_vehiculos")

        messages.error(request, "Error al guardar los cambios.")

    return redirect("vehiculos:lista_vehiculos")


def calcular_total_gastos(ficha):
    total = sum(
        float(v) for v in [
            ficha.gasto_f08,
            ficha.gasto_informes,
            ficha.gasto_patentes,
            ficha.gasto_verificacion,
            ficha.gasto_autopartes,
            ficha.gasto_vtv,
            ficha.gasto_r541,
            ficha.gasto_firmas,
        ] if v
    )
    ficha.total_gastos = total
    ficha.save(update_fields=["total_gastos"])


# ==========================================================
# FICHA COMPLETA
# ==========================================================
def ficha_completa(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    mapa_gastos = {
        "Formulario 08": ficha.gasto_f08,
        "Informes": ficha.gasto_informes,
        "Patentes": ficha.gasto_patentes,
        "Verificación": ficha.gasto_verificacion,
        "Autopartes": ficha.gasto_autopartes,
        "VTV": ficha.gasto_vtv,
        "R541": ficha.gasto_r541,
        "Firmas": ficha.gasto_firmas,
    }

    gastos_ingreso = []
    for concepto, monto in mapa_gastos.items():
        if not monto or monto <= 0:
            continue

        total_pagado = (
            PagoGastoIngreso.objects.filter(
                vehiculo=vehiculo,
                concepto=concepto
            ).aggregate(total=Sum("monto"))["total"]
            or Decimal("0")
        )

        gastos_ingreso.append({
            "concepto": concepto,
            "monto": monto,
            "total_pagado": total_pagado,
            "saldo": Decimal(monto) - total_pagado,
        })

    total_pendiente = sum(g["saldo"] for g in gastos_ingreso)

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
# REGISTRAR PAGO DE GASTO
# ==========================================================
@transaction.atomic
def registrar_pago_gasto(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    if request.method == "POST":
        fecha_pago = request.POST.get("fecha_pago")
        monto_raw = request.POST.get("monto")

        if monto_raw and Decimal(monto_raw) > 0 and not fecha_pago:
            messages.error(
                request,
                "Para registrar un pago es obligatorio ingresar la fecha."
            )
            return redirect(
                "vehiculos:ficha_completa",
                vehiculo_id=vehiculo.id
            )

        if not monto_raw or Decimal(monto_raw) <= 0:
            messages.error(
                request,
                "El monto del pago debe ser mayor a 0."
            )
            return redirect(
                "vehiculos:ficha_completa",
                vehiculo_id=vehiculo.id
            )

        PagoGastoIngreso.objects.create(
            vehiculo=vehiculo,
            concepto=request.POST.get("gasto_id"),
            fecha_pago=fecha_pago,
            monto=Decimal(monto_raw),
            observaciones=request.POST.get("observaciones"),
        )

        messages.success(request, "Pago de gasto registrado correctamente.")

    return redirect(
        "vehiculos:ficha_completa",
        vehiculo_id=vehiculo.id
    )
# ==========================================================
# PDF FICHA VEHICULAR (LIMPIO – SIN MENÚ)
# ==========================================================
def ficha_vehicular_pdf(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    ficha, _ = FichaVehicular.objects.get_or_create(vehiculo=vehiculo)

    html_string = render_to_string(
        "vehiculos/ficha_vehicular_pdf.html",
        {
            "vehiculo": vehiculo,
            "ficha": ficha,
        }
    )

    css = CSS(string="""
        @page { size: A4; margin: 2cm; }
        body { font-family: Arial, Helvetica, sans-serif; font-size: 12px; }
        h2 { text-align: center; color: #002855; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        td { padding: 6px; border: 1px solid #ccc; }
        .label { font-weight: bold; width: 35%; }
    """)

    pdf = HTML(
        string=html_string,
        base_url=request.build_absolute_uri()
    ).write_pdf(stylesheets=[css])

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="ficha_{vehiculo.dominio or vehiculo.id}.pdf"'
    )
    return response


# ==========================================================
# SINCRONIZAR TURNOS
# ==========================================================
def sincronizar_turnos_calendario(vehiculo, ficha):
    Evento.objects.filter(
        vehiculo=vehiculo,
        tipo__in=["vtv", "autopartes"]
    ).delete()

    if ficha.vtv_turno:
        Evento.objects.create(
            vehiculo=vehiculo,
            titulo=f"Turno VTV – {vehiculo}",
            fecha=ficha.vtv_turno,
            tipo="vtv",
        )

    if ficha.autopartes_turno:
        Evento.objects.create(
            vehiculo=vehiculo,
            titulo=f"Grabado autopartes – {vehiculo}",
            fecha=ficha.autopartes_turno,
            tipo="autopartes",
        )


# ==========================================================
# ELIMINAR VEHÍCULO (SIN DELETE)
# ==========================================================
def eliminar_vehiculo(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    from ventas.models import Venta

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
# REVERTIR VENTA
# ==========================================================
@transaction.atomic
def revertir_venta(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    from ventas.models import Venta
    from gestoria.models import Gestoria

    venta = Venta.objects.filter(
        vehiculo=vehiculo,
        estado__in=["pendiente", "confirmada"]
    ).first()

    if not venta:
        messages.error(request, "No hay una venta activa para revertir.")
        return redirect("vehiculos:lista_vehiculos")

    Gestoria.objects.filter(venta=venta).delete()

    venta.estado = "revertida"
    venta.save(update_fields=["estado"])

    vehiculo.estado = "stock"
    vehiculo.save(update_fields=["estado"])

    messages.success(
        request,
        "La venta fue revertida y el vehículo volvió a stock."
    )

    return redirect("vehiculos:lista_vehiculos")


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
        {
            "vehiculo": vehiculo,
        },
    )


# ==========================================================
# AJAX – DATOS DE VEHÍCULO (BOLETOS)
# ==========================================================
@login_required
def vehiculo_datos_ajax(request):
    vehiculo_id = request.GET.get("vehiculo_id")

    try:
        vehiculo = Vehiculo.objects.get(id=vehiculo_id)
    except Vehiculo.DoesNotExist:
        return JsonResponse({"error": "Vehículo no válido"}, status=400)

    ficha = FichaVehicular.objects.filter(vehiculo=vehiculo).first()

    return JsonResponse({
        "marca": vehiculo.marca or "",
        "modelo": vehiculo.modelo or "",
        "anio": vehiculo.anio or "",
        "patente": vehiculo.dominio or "",
        "motor": ficha.numero_motor if ficha and ficha.numero_motor else "",
        "chasis": ficha.numero_chasis if ficha and ficha.numero_chasis else "",
    })
