from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from cuentas.models import CuentaCorriente, MovimientoCuenta
from gestoria.models import Gestoria
from ventas.models import Venta
from vehiculos.models import Vehiculo


# ==========================================================
# 🔐 INGRESO (LOGIN)
# ==========================================================
def ingreso(request):

    if request.method == 'POST':
        # ✅ FIX: limpiar espacios invisibles
        usuario = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(
            request,
            username=usuario,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect('inicio')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "inicio/login.html")


# ==========================================================
# 🏠 INICIO / DASHBOARD
# ==========================================================
@login_required(login_url='ingreso')
def inicio(request):
    """
    Inicio del sistema:
    - Resumen general
    - Avisos de cuotas vencidas (según lógica contable real)
    - Gestoría vigente
    """

    hoy = timezone.now().date()

    # =============================
    # CUENTAS CON DEUDA
    # =============================
    cuentas_con_deuda_qs = CuentaCorriente.objects.filter(saldo__gt=0)

    cantidad_deudores = cuentas_con_deuda_qs.count()
    total_deuda = cuentas_con_deuda_qs.aggregate(
        total=Sum("saldo")
    )["total"] or 0

    top_cuentas_deuda = cuentas_con_deuda_qs.select_related(
        "cliente"
    ).order_by("-saldo")[:5]

    # =============================
    # ⚠️ AVISOS DE CUOTAS VENCIDAS
    # =============================
    movimientos_vencidos = (
        MovimientoCuenta.objects
        .filter(
            tipo="debe",
            fecha__lt=hoy,
            cuenta__saldo__gt=0
        )
        .select_related(
            "cuenta",
            "cuenta__cliente",
            "cuenta__venta"
        )
    )

    avisos_cuotas = (
        movimientos_vencidos
        .values(
            "cuenta__cliente__nombre_completo",
            "cuenta__venta__id"
        )
        .annotate(
            cantidad=Count("id"),
            monto=Sum("monto")
        )
        .order_by("-monto")
    )

    # =============================
    # GESTORÍA VIGENTE
    # =============================
    gestoria_vigente_qs = Gestoria.objects.filter(
        estado="vigente"
    ).select_related("cliente", "vehiculo")

    transferencias_vigentes = gestoria_vigente_qs.count()
    top_gestoria_vigente = gestoria_vigente_qs.order_by(
        "-fecha_creacion"
    )[:5]

    # =============================
    # ESTADO GENERAL
    # =============================
    vehiculos_stock = Vehiculo.objects.filter(
        estado="stock"
    ).count()

    ventas_activas = Venta.objects.exclude(
        estado="finalizada"
    ).count()

    # =============================
    # CONTEXTO FINAL
    # =============================
    context = {
        # Deuda
        "cantidad_deudores": cantidad_deudores,
        "total_deuda": total_deuda,
        "top_cuentas_deuda": top_cuentas_deuda,

        # Avisos cuotas
        "avisos_cuotas": avisos_cuotas,

        # Gestoría
        "transferencias_vigentes": transferencias_vigentes,
        "top_gestoria_vigente": top_gestoria_vigente,

        # Estado general
        "ventas_activas": ventas_activas,
        "vehiculos_stock": vehiculos_stock,
    }

    return render(request, "inicio/inicio.html", context)


# ==========================================================
# 🚪 CERRAR SESIÓN
# ==========================================================
def cerrar_sesion(request):
    """
    Cierra la sesión del usuario y vuelve al login.
    """
    logout(request)
    return redirect('ingreso')