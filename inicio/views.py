from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from cuentas.models import CuentaCorriente, MovimientoCuenta
from gestoria.models import Gestoria
from ventas.models import Venta
from vehiculos.models import Vehiculo, FichaVehicular
from crm.models import Prospecto


# ==========================================================
# 🔐 INGRESO (LOGIN)
# ==========================================================
def ingreso(request):
    if request.method == 'POST':
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
    hoy = timezone.now().date()
    proximos_30_dias = hoy + timedelta(days=30)

    # =============================
    # CUENTAS CON DEUDA
    # =============================
    cuentas_con_deuda_qs = CuentaCorriente.objects.filter(saldo__gt=0)
    cantidad_deudores = cuentas_con_deuda_qs.count()
    total_deuda = cuentas_con_deuda_qs.aggregate(total=Sum("saldo"))["total"] or 0
    top_cuentas_deuda = cuentas_con_deuda_qs.select_related("cliente").order_by("-saldo")[:5]

    # =============================
    # GESTORÍA VIGENTE
    # =============================
    gestoria_vigente_qs = Gestoria.objects.filter(estado="vigente").select_related("cliente", "vehiculo")
    transferencias_vigentes = gestoria_vigente_qs.count()
    top_gestoria_vigente = gestoria_vigente_qs.order_by("-fecha_creacion")[:5]

    # =============================
    # ESTADO GENERAL
    # =============================
    vehiculos_stock = Vehiculo.objects.filter(estado="stock").count()
    vehiculos_temporal = Vehiculo.objects.filter(estado="temporal").count()
    vehiculos_vendidos_mes = Vehiculo.objects.filter(
        estado="vendido",
        venta__fecha_venta__year=hoy.year,
        venta__fecha_venta__month=hoy.month
    ).count()

    ventas_activas = Venta.objects.filter(estado__in=["pendiente", "confirmada"]).count()
    ventas_mes = Venta.objects.filter(
        fecha_venta__year=hoy.year,
        fecha_venta__month=hoy.month
    ).count()

    # =============================
    # ÚLTIMAS VENTAS
    # =============================
    ultimas_ventas = Venta.objects.filter(
        estado="confirmada"
    ).select_related("vehiculo", "cliente").order_by("-fecha_venta")[:5]

    # =============================
    # VENCIMIENTOS PRÓXIMOS (30 días)
    # =============================
    vencimientos_vtv = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
        vtv_vencimiento__gte=hoy,
        vtv_vencimiento__lte=proximos_30_dias
    ).select_related("vehiculo").order_by("vtv_vencimiento")[:5]

    vencimientos_verificacion = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
        verificacion_vencimiento__gte=hoy,
        verificacion_vencimiento__lte=proximos_30_dias
    ).select_related("vehiculo").order_by("verificacion_vencimiento")[:5]

    # Vencimientos vencidos (ya pasaron)
    vtv_vencidos = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
        vtv_vencimiento__lt=hoy
    ).count()

    verificacion_vencidos = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
        verificacion_vencimiento__lt=hoy
    ).count()

    # =============================
    # TURNOS PRÓXIMOS (7 días)
    # =============================
    proximos_7_dias = hoy + timedelta(days=7)
    
    turnos_vtv = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
        vtv_turno__gte=hoy,
        vtv_turno__lte=proximos_7_dias
    ).select_related("vehiculo").order_by("vtv_turno")[:3]

    turnos_verificacion = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
        verificacion_turno__gte=hoy,
        verificacion_turno__lte=proximos_7_dias
    ).select_related("vehiculo").order_by("verificacion_turno")[:3]

    turnos_autopartes = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
        autopartes_turno__gte=hoy,
        autopartes_turno__lte=proximos_7_dias
    ).select_related("vehiculo").order_by("autopartes_turno")[:3]

    # =============================
    # CUOTAS VENCIDAS
    # =============================
    cuotas_vencidas_count = MovimientoCuenta.objects.filter(
        tipo="debe",
        fecha__lt=hoy,
        cuenta__saldo__gt=0
    ).count()

    # =============================
    # CRM – RECORDATORIOS
    # =============================
    crm_contactos_pendientes = Prospecto.objects.filter(
        fecha_proximo_contacto__lte=hoy,
        etapa__in=["nuevo", "contactado", "en_negociacion", "presupuestado"],
    ).select_related("vehiculo_interes").order_by("fecha_proximo_contacto")[:5]

    crm_nuevos = Prospecto.objects.filter(etapa="nuevo").count()

    crm_en_negociacion = Prospecto.objects.filter(
        etapa__in=["contactado", "en_negociacion", "presupuestado"],
    ).count()

    crm_total_activos = Prospecto.objects.exclude(
        etapa__in=["ganado", "perdido"],
    ).count()

    # =============================
    # CONTEXTO FINAL
    # =============================
    context = {
        # Resumen principal
        "cantidad_deudores": cantidad_deudores,
        "total_deuda": total_deuda,
        "top_cuentas_deuda": top_cuentas_deuda,
        
        # Gestoría
        "transferencias_vigentes": transferencias_vigentes,
        "top_gestoria_vigente": top_gestoria_vigente,
        
        # Stock y ventas
        "vehiculos_stock": vehiculos_stock,
        "vehiculos_temporal": vehiculos_temporal,
        "vehiculos_vendidos_mes": vehiculos_vendidos_mes,
        "ventas_activas": ventas_activas,
        "ventas_mes": ventas_mes,
        "ultimas_ventas": ultimas_ventas,
        
        # Vencimientos
        "vencimientos_vtv": vencimientos_vtv,
        "vencimientos_verificacion": vencimientos_verificacion,
        "vtv_vencidos": vtv_vencidos,
        "verificacion_vencidos": verificacion_vencidos,
        
        # Turnos
        "turnos_vtv": turnos_vtv,
        "turnos_verificacion": turnos_verificacion,
        "turnos_autopartes": turnos_autopartes,
        
        # Cuotas
        "cuotas_vencidas_count": cuotas_vencidas_count,

        # CRM
        "crm_contactos_pendientes": crm_contactos_pendientes,
        "crm_nuevos": crm_nuevos,
        "crm_en_negociacion": crm_en_negociacion,
        "crm_total_activos": crm_total_activos,

        # Fecha
        "hoy": hoy,
    }

    return render(request, "inicio/inicio.html", context)


# ==========================================================
# 🚪 CERRAR SESIÓN
# ==========================================================
def cerrar_sesion(request):
    logout(request)
    return redirect('ingreso')