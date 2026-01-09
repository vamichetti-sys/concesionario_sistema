from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse

from .models import Cliente
from .forms import ClienteForm
from cuentas.models import CuentaCorriente, CuotaPlan
from ventas.models import Venta
from boletos.models import BoletoCompraventa


# ==========================================================
# LISTA DE CLIENTES
# ==========================================================
@login_required(login_url='ingreso')
def lista_clientes(request):
    query = request.GET.get('q', '')

    clientes = Cliente.objects.filter(activo=True).order_by('nombre_completo')

    if query:
        clientes = clientes.filter(
            Q(nombre_completo__icontains=query) |
            Q(telefono__icontains=query) |
            Q(email__icontains=query)
        )

    hoy = timezone.now().date()
    clientes_con_estado = []

    for cliente in clientes:
        estado_pago = 'verde'
        dias_mora = 0

        # 👉 SOLO CUENTA ACTIVA (no cerrada)
        cuenta_activa = (
            CuentaCorriente.objects
            .filter(cliente=cliente)
            .exclude(estado='cerrada')
            .first()
        )

        if cuenta_activa:
            cuotas_vencidas = CuotaPlan.objects.filter(
                plan__cuenta=cuenta_activa,
                estado='pendiente',
                vencimiento__lt=hoy
            )

            if cuotas_vencidas.exists():
                cuota_mas_antigua = cuotas_vencidas.order_by('vencimiento').first()
                dias_mora = (hoy - cuota_mas_antigua.vencimiento).days

                if dias_mora <= 30:
                    estado_pago = 'amarillo'
                else:
                    estado_pago = 'rojo'

        clientes_con_estado.append({
            'cliente': cliente,
            'estado_pago': estado_pago,
            'dias_mora': dias_mora,
        })

    return render(
        request,
        'clientes/lista_clientes.html',
        {
            'clientes_con_estado': clientes_con_estado,
            'query': query,
        }
    )


# ==========================================================
# ALTA DE CLIENTE
# ==========================================================
@login_required(login_url='ingreso')
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente creado correctamente.")
            return redirect('clientes:lista_clientes')
    else:
        form = ClienteForm()

    return render(
        request,
        'clientes/crear_cliente.html',
        {
            'form': form
        }
    )


# ==========================================================
# DETALLE / FICHA DE CLIENTE
# (CUENTA ACTIVA + HISTORIAL + BOLETOS PDF)
# ==========================================================
@login_required(login_url='ingreso')
def detalle_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # ===============================
    # CUENTA ACTIVA (al_dia / deuda)
    # ===============================
    cuenta_activa = (
        CuentaCorriente.objects
        .filter(cliente=cliente)
        .exclude(estado='cerrada')
        .first()
    )

    # ===============================
    # HISTORIAL (cuentas cerradas)
    # ===============================
    cuentas_historial = (
        CuentaCorriente.objects
        .filter(cliente=cliente, estado='cerrada')
        .select_related('venta', 'venta__vehiculo')
        .order_by('-creada')
    )

    # ===============================
    # BOLETOS DEL CLIENTE (PDF)
    # ===============================
    boletos = (
        BoletoCompraventa.objects
        .filter(cliente=cliente)
        .select_related('vehiculo', 'cuenta_corriente')
        .order_by('-creado')
    )

    tiene_venta_0km = Venta.objects.filter(
        cliente=cliente,
        vehiculo__es_0km=True
    ).exists()

    return render(
        request,
        'clientes/detalle_cliente.html',
        {
            'cliente': cliente,
            'cuenta_activa': cuenta_activa,
            'cuentas_historial': cuentas_historial,
            'boletos': boletos,
            'tiene_venta_0km': tiene_venta_0km,
        }
    )
# ==========================================================
# EDITAR CLIENTE
# ==========================================================
@login_required(login_url='ingreso')
def editar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Datos del cliente actualizados correctamente."
            )
            return redirect(
                'clientes:detalle_cliente',
                cliente_id=cliente.id
            )
    else:
        form = ClienteForm(instance=cliente)

    return render(
        request,
        'clientes/editar_cliente.html',
        {
            'cliente': cliente,
            'form': form
        }
    )


# ==========================================================
# DESACTIVAR CLIENTE (ELIMINACIÓN LÓGICA)
# ==========================================================
@login_required(login_url='ingreso')
def desactivar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    cliente.activo = False
    cliente.save()

    messages.success(
        request,
        f"El cliente {cliente.nombre_completo} fue desactivado correctamente."
    )

    return redirect('clientes:lista_clientes')


# ==========================================================
# API CLIENTE
# ==========================================================
@login_required(login_url='ingreso')
def cliente_json(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    return JsonResponse({
        "nombre_completo": cliente.nombre_completo,
        "dni": cliente.dni_cuit or "",
        "direccion": cliente.direccion or "",
    })


# ==========================================================
# API CLIENTE (BOLETOS – AUTOCOMPLETADO)
# ==========================================================
@login_required(login_url='ingreso')
def cliente_datos_ajax(request):
    cliente_id = request.GET.get("cliente_id")

    try:
        cliente = Cliente.objects.get(id=cliente_id, activo=True)
    except Cliente.DoesNotExist:
        return JsonResponse({"error": "Cliente no válido"}, status=400)

    return JsonResponse({
        "nombre_completo": cliente.nombre_completo or "",
        "dni": cliente.dni_cuit or "",
        "domicilio": cliente.direccion or "",
    })


# ==========================================================
# HISTORIAL DE FINANCIACIÓN (CUENTA CERRADA)
# ==========================================================
@login_required
def historial_financiacion(request, cuenta_id):
    cuenta = get_object_or_404(
        CuentaCorriente.objects.select_related(
            'cliente',
            'venta',
            'venta__vehiculo'
        ),
        id=cuenta_id,
        estado='cerrada'
    )

    plan = getattr(cuenta, 'plan_pago', None)
    cuotas = plan.cuotas.all().order_by('numero') if plan else []

    return render(
        request,
        'cuentas/historial_financiacion.html',
        {
            'cuenta': cuenta,
            'plan': plan,
            'cuotas': cuotas,
        }
    )
