from datetime import date
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum

from .models import CuentaInterna, MovimientoInterno, Alquiler, PagoAlquiler
from .forms import (
    CuentaInternaForm, MovimientoInternoForm, AlquilerForm, PagoAlquilerForm,
)


def usuario_autorizado(user):
    return user.is_staff or user.has_perm('cuentas_internas.view_cuentainterna')


@login_required
def lista_cuentas(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    query = request.GET.get('q', '')
    mostrar = request.GET.get('mostrar', 'activas')
    
    cuentas = CuentaInterna.objects.all()
    
    if mostrar == 'activas':
        cuentas = cuentas.filter(activa=True)
    elif mostrar == 'inactivas':
        cuentas = cuentas.filter(activa=False)
    
    if query:
        cuentas = cuentas.filter(
            Q(nombre__icontains=query) |
            Q(cargo__icontains=query)
        )
    
    total_deudas = CuentaInterna.objects.filter(activa=True, saldo__gt=0).aggregate(Sum('saldo'))['saldo__sum'] or 0
    total_favor = CuentaInterna.objects.filter(activa=True, saldo__lt=0).aggregate(Sum('saldo'))['saldo__sum'] or 0
    
    return render(request, 'cuentas_internas/lista.html', {
        'cuentas': cuentas,
        'query': query,
        'mostrar': mostrar,
        'total_deudas': total_deudas,
        'total_favor': abs(total_favor),
    })


@login_required
def crear_cuenta(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    if request.method == 'POST':
        form = CuentaInternaForm(request.POST)
        if form.is_valid():
            cuenta = form.save()
            
            saldo_inicial = request.POST.get('saldo_inicial', 0)
            try:
                saldo_inicial = float(saldo_inicial)
                if saldo_inicial != 0:
                    from datetime import date
                    tipo = 'debe' if saldo_inicial > 0 else 'haber'
                    MovimientoInterno.objects.create(
                        cuenta=cuenta,
                        tipo=tipo,
                        monto=abs(saldo_inicial),
                        concepto='Saldo inicial',
                        fecha=date.today(),
                        creado_por=request.user
                    )
            except ValueError:
                pass
            
            messages.success(request, f'Cuenta "{cuenta.nombre}" creada.')
            return redirect('cuentas_internas:detalle', pk=cuenta.pk)
    else:
        form = CuentaInternaForm()
    
    return render(request, 'cuentas_internas/form.html', {
        'form': form,
        'titulo': 'Nueva Cuenta Interna',
    })


@login_required
def detalle_cuenta(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cuenta = get_object_or_404(CuentaInterna, pk=pk)
    movimientos = cuenta.movimientos.all()
    
    return render(request, 'cuentas_internas/detalle.html', {
        'cuenta': cuenta,
        'movimientos': movimientos,
    })


@login_required
def editar_cuenta(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cuenta = get_object_or_404(CuentaInterna, pk=pk)
    
    if request.method == 'POST':
        form = CuentaInternaForm(request.POST, instance=cuenta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cuenta actualizada.')
            return redirect('cuentas_internas:detalle', pk=cuenta.pk)
    else:
        form = CuentaInternaForm(instance=cuenta)
    
    return render(request, 'cuentas_internas/form.html', {
        'form': form,
        'titulo': f'Editar {cuenta.nombre}',
        'cuenta': cuenta,
    })


@login_required
def eliminar_cuenta(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cuenta = get_object_or_404(CuentaInterna, pk=pk)
    
    if request.method == 'POST':
        nombre = cuenta.nombre
        cuenta.delete()
        messages.success(request, f'Cuenta "{nombre}" eliminada.')
        return redirect('cuentas_internas:lista')
    
    return render(request, 'cuentas_internas/eliminar.html', {'cuenta': cuenta})


@login_required
def agregar_movimiento(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cuenta = get_object_or_404(CuentaInterna, pk=pk)
    
    if request.method == 'POST':
        form = MovimientoInternoForm(request.POST)
        if form.is_valid():
            movimiento = form.save(commit=False)
            movimiento.cuenta = cuenta
            movimiento.creado_por = request.user
            movimiento.save()
            messages.success(request, 'Movimiento registrado.')
            return redirect('cuentas_internas:detalle', pk=cuenta.pk)
    else:
        form = MovimientoInternoForm()
    
    return render(request, 'cuentas_internas/movimiento_form.html', {
        'form': form,
        'cuenta': cuenta,
    })


@login_required
def eliminar_movimiento(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    movimiento = get_object_or_404(MovimientoInterno, pk=pk)
    cuenta = movimiento.cuenta
    
    if request.method == 'POST':
        movimiento.delete()
        messages.success(request, 'Movimiento eliminado.')
        return redirect('cuentas_internas:detalle', pk=cuenta.pk)
    
    return render(request, 'cuentas_internas/eliminar_movimiento.html', {
        'movimiento': movimiento,
        'cuenta': cuenta,
    })

# ==========================================================
# PDF MENSUAL: movimientos del mes/año de todas las cuentas
# ==========================================================
@login_required
def pdf_mensual(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    from reportes.pdf_utils import render_pdf_listado, MESES_ES

    hoy = date.today()
    try:
        mes = int(request.GET.get('mes', hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month
    try:
        anio = int(request.GET.get('anio', hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year

    movs = (
        MovimientoInterno.objects
        .filter(fecha__year=anio, fecha__month=mes)
        .select_related('cuenta')
        .order_by('fecha', 'cuenta__nombre')
    )

    total_debe = Decimal('0')
    total_haber = Decimal('0')
    filas = []
    for m in movs:
        signo = m.monto if m.tipo == 'debe' else -m.monto
        if m.tipo == 'debe':
            total_debe += m.monto
        else:
            total_haber += m.monto
        filas.append([
            m.fecha.strftime('%d/%m/%Y'),
            m.cuenta.nombre,
            m.concepto or '-',
            m.get_tipo_display(),
            f"$ {m.monto:,.0f}".replace(',', '.'),
        ])

    saldo_neto = total_debe - total_haber
    totales = [
        '', '', 'TOTALES',
        f"Debe: $ {total_debe:,.0f}".replace(',', '.'),
        f"Neto: $ {saldo_neto:,.0f}".replace(',', '.'),
    ]

    return render_pdf_listado(
        filename=f"cuentas_internas_{mes:02d}_{anio}.pdf",
        titulo="Cuentas Internas",
        subtitulo=f"{MESES_ES[mes]} {anio} – {len(filas)} movimiento(s)",
        columnas=['Fecha', 'Cuenta', 'Concepto', 'Tipo', 'Monto'],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {hoy.strftime('%d/%m/%Y')}",
    )


# ==========================================================
# HUB: Cuentas Internas / Alquileres
# ==========================================================
@login_required
def hub(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    total_cuentas = CuentaInterna.objects.filter(activa=True).count()
    total_alquileres = Alquiler.objects.filter(activo=True).count()
    total_mensual_alquileres = (
        Alquiler.objects.filter(activo=True).aggregate(t=Sum('monto_mensual'))['t'] or 0
    )
    return render(request, 'cuentas_internas/hub.html', {
        'total_cuentas': total_cuentas,
        'total_alquileres': total_alquileres,
        'total_mensual_alquileres': total_mensual_alquileres,
    })


# ==========================================================
# ALQUILERES
# ==========================================================
@login_required
def alquileres_lista(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    query = request.GET.get('q', '')
    mostrar = request.GET.get('mostrar', 'activos')

    alquileres = Alquiler.objects.all()
    if mostrar == 'activos':
        alquileres = alquileres.filter(activo=True)
    elif mostrar == 'inactivos':
        alquileres = alquileres.filter(activo=False)
    if query:
        alquileres = alquileres.filter(
            Q(nombre__icontains=query) |
            Q(direccion__icontains=query) |
            Q(arrendatario__icontains=query)
        )

    # Ordenado por arrendatario para agrupar en el template
    alquileres = alquileres.order_by('arrendatario', 'nombre')

    total_mensual = (
        Alquiler.objects.filter(activo=True).aggregate(t=Sum('monto_mensual'))['t'] or 0
    )

    return render(request, 'cuentas_internas/alquileres_lista.html', {
        'alquileres': alquileres,
        'query': query,
        'mostrar': mostrar,
        'total_mensual': total_mensual,
        'hoy': date.today(),
    })


@login_required
def alquileres_pdf(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    from reportes.pdf_utils import render_pdf_listado

    query = request.GET.get('q', '')
    mostrar = request.GET.get('mostrar', 'activos')
    alquileres = Alquiler.objects.all()
    if mostrar == 'activos':
        alquileres = alquileres.filter(activo=True)
    elif mostrar == 'inactivos':
        alquileres = alquileres.filter(activo=False)
    if query:
        alquileres = alquileres.filter(
            Q(nombre__icontains=query) |
            Q(direccion__icontains=query) |
            Q(arrendatario__icontains=query)
        )
    alquileres = alquileres.order_by('arrendatario', 'nombre')

    total = Decimal('0')
    filas = []
    for a in alquileres:
        total += a.monto_mensual or Decimal('0')
        filas.append([
            a.arrendatario or '—',
            a.nombre,
            f"$ {(a.monto_mensual or 0):,.0f}".replace(',', '.'),
            str(a.dia_pago) if a.dia_pago else '—',
            'Pagado' if a.pagado_mes_actual else 'Pendiente',
        ])

    totales = ['', 'TOTAL', f"$ {total:,.0f}".replace(',', '.'), '', '']

    return render_pdf_listado(
        filename='alquileres.pdf',
        titulo='Alquileres por arrendatario',
        subtitulo=f"{len(filas)} alquiler(es) · total mensual a cobrar incluido",
        columnas=['Arrendatario', 'Inmueble', 'Monto mensual', 'Día cobro', 'Mes actual'],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {date.today().strftime('%d/%m/%Y')}",
    )


@login_required
def alquiler_crear(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    if request.method == 'POST':
        form = AlquilerForm(request.POST, request.FILES)
        if form.is_valid():
            alq = form.save()
            messages.success(request, f'Alquiler "{alq.nombre}" creado.')
            return redirect('cuentas_internas:alquiler_detalle', pk=alq.pk)
    else:
        form = AlquilerForm()
    return render(request, 'cuentas_internas/alquiler_form.html', {
        'form': form, 'titulo': 'Nuevo alquiler',
    })


@login_required
def alquiler_editar(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    alq = get_object_or_404(Alquiler, pk=pk)
    if request.method == 'POST':
        form = AlquilerForm(request.POST, request.FILES, instance=alq)
        if form.is_valid():
            form.save()
            messages.success(request, 'Alquiler actualizado.')
            return redirect('cuentas_internas:alquiler_detalle', pk=alq.pk)
    else:
        form = AlquilerForm(instance=alq)
    return render(request, 'cuentas_internas/alquiler_form.html', {
        'form': form, 'titulo': f'Editar — {alq.nombre}', 'alquiler': alq,
    })


@login_required
def alquiler_eliminar(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    alq = get_object_or_404(Alquiler, pk=pk)
    if request.method == 'POST':
        nombre = alq.nombre
        alq.delete()
        messages.success(request, f'Alquiler "{nombre}" eliminado.')
        return redirect('cuentas_internas:alquileres_lista')
    return render(request, 'cuentas_internas/alquiler_eliminar.html', {'alquiler': alq})


@login_required
def alquiler_detalle(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    alq = get_object_or_404(Alquiler, pk=pk)
    pagos = alq.pagos.all()

    if request.method == 'POST':
        form = PagoAlquilerForm(request.POST)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.alquiler = alq
            pago.creado_por = request.user
            pago.save()

            # La cobranza del alquiler se registra como Ingreso Personal del
            # usuario que cobra (vinculado al pago: si se borra el cobro, se
            # borra el ingreso por cascada).
            from gastos_personales.models import IngresoPersonal
            IngresoPersonal.objects.create(
                usuario=request.user,
                pago_alquiler=pago,
                concepto=f"Alquiler – {alq.nombre}",
                descripcion=alq.arrendatario or "",
                monto=pago.monto,
                mes=pago.periodo_mes or pago.fecha.month,
                anio=pago.periodo_anio or pago.fecha.year,
                fecha=pago.fecha,
            )

            messages.success(request, f'Cobro de ${pago.monto} registrado y cargado en Ingresos Personales.')
            return redirect('cuentas_internas:alquiler_detalle', pk=alq.pk)
    else:
        hoy = date.today()
        def _gint(name, default):
            try:
                return int(request.GET.get(name, default))
            except (TypeError, ValueError):
                return default
        form = PagoAlquilerForm(initial={
            'fecha': hoy,
            'monto': alq.monto_mensual or None,
            'forma_pago': 'transferencia',
            'periodo_mes': _gint('mes', hoy.month),
            'periodo_anio': _gint('anio', hoy.year),
        })

    cronograma = alq.cronograma()
    meses_cobrados = sum(1 for f in cronograma if f['cobrado'])

    return render(request, 'cuentas_internas/alquiler_detalle.html', {
        'alquiler': alq,
        'pagos': pagos,
        'form': form,
        'cronograma': cronograma,
        'meses_cobrados': meses_cobrados,
        'meses_total': len(cronograma),
    })


@login_required
def alquiler_pago_eliminar(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    pago = get_object_or_404(PagoAlquiler, pk=pk)
    alquiler_pk = pago.alquiler_id
    if request.method == 'POST':
        pago.delete()
        messages.success(request, 'Pago eliminado.')
    return redirect('cuentas_internas:alquiler_detalle', pk=alquiler_pk)
