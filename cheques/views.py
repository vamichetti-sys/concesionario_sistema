from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from datetime import date, timedelta

from .models import Cheque
from .forms import ChequeForm


def _revertir_cobro_de_cheque(cheque, usuario=None):
    """
    Si el cheque saldó un cobro (cheque.cobro = cuentas.Pago), revierte ese
    cobro con el mismo patrón que `eliminar_pago`: borra sus movimientos,
    reabre las cuotas, reactiva el plan y recalcula el saldo. Devuelve True si
    revirtió algo. Se llama dentro de una vista @transaction.atomic.
    """
    pago = cheque.cobro
    if pago is None:
        return False

    from cuentas.models import CuotaPlan

    cuenta = pago.cuenta
    cuotas_afectadas = list(CuotaPlan.objects.filter(pagos__pago=pago).distinct())
    recibo = pago.numero_recibo

    # Borrar el rastro contable del cobro
    pago.movimientos_creados.all().delete()
    # Desvincular el cheque antes de borrar el pago
    cheque.cobro = None
    cheque.save(update_fields=["cobro"])
    pago.delete()

    # Reabrir cuotas que quedaron "pagadas" pero con saldo pendiente
    for cuota in cuotas_afectadas:
        if cuota.saldo_pendiente > 0 and cuota.estado == "pagada":
            cuota.estado = "pendiente"
            cuota.save(update_fields=["estado"])

    # Reactivar el plan si estaba finalizado y volvió a tener cuotas pendientes
    plan = getattr(cuenta, "plan_pago", None)
    if plan and plan.estado == "finalizado" and plan.cuotas.filter(estado="pendiente").exists():
        plan.estado = "activo"
        plan.save(update_fields=["estado"])

    cuenta.recalcular_saldo()
    try:
        cuenta.log("Cheque rechazado", f"Recibo {recibo} revertido (cheque #{cheque.numero_cheque})")
    except Exception:
        pass
    return True


def usuario_autorizado(user):
    return user.is_staff or user.has_perm('cheques.view_cheque')


@login_required
def lista_cheques(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    query = request.GET.get('q', '')
    estado_filtro = request.GET.get('estado', '')
    rango_filtro = request.GET.get('rango', '')
    
    cheques = Cheque.objects.all()
    
    if query:
        cheques = cheques.filter(
            Q(numero_cheque__icontains=query) |
            Q(titular_cheque__icontains=query) |
            Q(cliente__icontains=query) |
            Q(banco_emision__icontains=query)
        )
    
    if estado_filtro:
        cheques = cheques.filter(estado=estado_filtro)
    
    # Filtro por rango de vencimiento
    if rango_filtro:
        hoy = date.today()
        if rango_filtro == 'vencido':
            cheques = cheques.filter(estado='a_depositar', fecha_deposito__lt=hoy)
        elif rango_filtro == 'hoy':
            cheques = cheques.filter(estado='a_depositar', fecha_deposito=hoy)
        elif rango_filtro == 'd1_7':
            cheques = cheques.filter(estado='a_depositar', fecha_deposito__gt=hoy, fecha_deposito__lte=hoy + timedelta(days=7))
        elif rango_filtro == 'd8_15':
            cheques = cheques.filter(estado='a_depositar', fecha_deposito__gt=hoy + timedelta(days=7), fecha_deposito__lte=hoy + timedelta(days=15))
        elif rango_filtro == 'd16_30':
            cheques = cheques.filter(estado='a_depositar', fecha_deposito__gt=hoy + timedelta(days=15), fecha_deposito__lte=hoy + timedelta(days=30))
        elif rango_filtro == 'd31_60':
            cheques = cheques.filter(estado='a_depositar', fecha_deposito__gt=hoy + timedelta(days=30), fecha_deposito__lte=hoy + timedelta(days=60))
        elif rango_filtro == 'mas60':
            cheques = cheques.filter(estado='a_depositar', fecha_deposito__gt=hoy + timedelta(days=60))
    
    # Resumen por vencimiento
    rangos, total_monto, total_cantidad = Cheque.resumen_por_vencimiento()
    
    # Contadores por estado
    total_a_depositar = Cheque.objects.filter(estado='a_depositar').aggregate(Sum('monto'))['monto__sum'] or 0
    total_depositado = Cheque.objects.filter(estado='depositado').aggregate(Sum('monto'))['monto__sum'] or 0
    total_endosado = Cheque.objects.filter(estado='endosado').aggregate(Sum('monto'))['monto__sum'] or 0
    total_rechazado = Cheque.objects.filter(estado='rechazado').aggregate(Sum('monto'))['monto__sum'] or 0
    
    return render(request, 'cheques/lista.html', {
        'cheques': cheques,
        'query': query,
        'estado_filtro': estado_filtro,
        'rango_filtro': rango_filtro,
        'rangos': rangos,
        'total_monto': total_monto,
        'total_cantidad': total_cantidad,
        'total_a_depositar': total_a_depositar,
        'total_depositado': total_depositado,
        'total_endosado': total_endosado,
        'total_rechazado': total_rechazado,
        'fecha_hoy': date.today(),
    })


@login_required
def crear_cheque(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    if request.method == 'POST':
        form = ChequeForm(request.POST)
        if form.is_valid():
            cheque = form.save(commit=False)
            cheque.creado_por = request.user
            cheque.save()
            messages.success(request, f'Cheque #{cheque.numero_cheque} registrado.')
            return redirect('cheques:lista')
    else:
        form = ChequeForm(initial={'fecha_ingreso': date.today()})
    
    return render(request, 'cheques/form.html', {
        'form': form,
        'titulo': 'Nuevo Cheque',
    })


@login_required
def editar_cheque(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cheque = get_object_or_404(Cheque, pk=pk)
    
    if request.method == 'POST':
        form = ChequeForm(request.POST, instance=cheque)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cheque actualizado.')
            return redirect('cheques:lista')
    else:
        form = ChequeForm(instance=cheque)
    
    return render(request, 'cheques/form.html', {
        'form': form,
        'titulo': f'Editar Cheque #{cheque.numero_cheque}',
        'cheque': cheque,
    })


@login_required
def eliminar_cheque(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cheque = get_object_or_404(Cheque, pk=pk)
    
    if request.method == 'POST':
        numero = cheque.numero_cheque
        cheque.delete()
        messages.success(request, f'Cheque #{numero} eliminado.')
        return redirect('cheques:lista')
    
    return render(request, 'cheques/eliminar.html', {'cheque': cheque})


@login_required
@transaction.atomic
def cambiar_estado_cheque(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')

    cheque = get_object_or_404(Cheque, pk=pk)
    if request.method != 'POST':
        return redirect('cheques:lista')

    nuevo_estado = request.POST.get('estado')
    if nuevo_estado not in ('a_depositar', 'depositado', 'endosado', 'rechazado'):
        messages.error(request, 'Estado inválido.')
        return redirect('cheques:lista')

    # ── DEPOSITADO ──
    if nuevo_estado == 'depositado':
        depositado_en = (request.POST.get('depositado_en') or '').strip()
        cheque.estado = 'depositado'
        cheque.depositado_en = depositado_en
        cheque.save(update_fields=['estado', 'depositado_en'])
        cheque.registrar_movimiento(
            'depositado', usuario=request.user,
            detalle=(f"Depositado en {depositado_en}" if depositado_en else "Depositado"),
        )
        messages.success(request, f'Cheque #{cheque.numero_cheque} marcado como depositado.')

    # ── ENDOSADO (destinatario OBLIGATORIO) ──
    elif nuevo_estado == 'endosado':
        destinatario = (request.POST.get('destinatario_endoso') or '').strip()
        if not destinatario:
            messages.error(request, 'Para endosar el cheque es obligatorio indicar a quién se lo entregaste.')
            return redirect('cheques:lista')
        fecha_endoso = request.POST.get('fecha_endoso') or date.today()
        cheque.estado = 'endosado'
        cheque.fecha_endoso = fecha_endoso
        cheque.destinatario_endoso = destinatario
        cheque.save(update_fields=['estado', 'fecha_endoso', 'destinatario_endoso'])
        cheque.registrar_movimiento(
            'endosado', usuario=request.user, destinatario=destinatario,
            detalle=f"Endosado a {destinatario}",
        )
        messages.success(request, f'Cheque #{cheque.numero_cheque} endosado a {destinatario}.')

    # ── RECHAZADO (revierte el cobro si lo había) ──
    elif nuevo_estado == 'rechazado':
        revertido = _revertir_cobro_de_cheque(cheque, request.user)
        cheque.estado = 'rechazado'
        cheque.save(update_fields=['estado'])
        detalle = "Rechazado por el banco"
        if revertido:
            detalle += " · cobro revertido (la deuda del cliente volvió a subir)"
        cheque.registrar_movimiento('rechazado', usuario=request.user, detalle=detalle)
        if revertido:
            messages.warning(
                request,
                f'Cheque #{cheque.numero_cheque} rechazado. Se revirtió el cobro: '
                'la cuota se reabrió y la deuda del cliente volvió a subir.'
            )
        else:
            messages.warning(request, f'Cheque #{cheque.numero_cheque} rechazado.')

    # ── VOLVER A "A DEPOSITAR" ──
    else:
        cheque.estado = 'a_depositar'
        cheque.save(update_fields=['estado'])
        cheque.registrar_movimiento('a_depositar', usuario=request.user, detalle='Volvió a "a depositar"')
        messages.success(request, f'Cheque #{cheque.numero_cheque} vuelto a "a depositar".')

    return redirect('cheques:lista')

# ==========================================================
# PDF: cheques a cobrar (estado='a_depositar')
# ==========================================================
from django.contrib.auth.decorators import login_required as _login_required_pdf

@_login_required_pdf
def pdf_a_cobrar(request):
    if not usuario_autorizado(request.user):
        from django.contrib import messages as _msgs
        from django.shortcuts import redirect as _redirect
        _msgs.error(request, 'No tenés permiso para acceder a esta sección.')
        return _redirect('inicio')

    from datetime import date as _date
    from decimal import Decimal as _Dec
    from reportes.pdf_utils import render_pdf_listado
    from .models import Cheque

    hoy = _date.today()

    qs = Cheque.objects.filter(estado='a_depositar').order_by('fecha_deposito', '-monto')

    total = _Dec('0')
    filas = []
    for c in qs:
        total += c.monto or _Dec('0')
        dias = (c.fecha_deposito - hoy).days if c.fecha_deposito else 0
        cuando = (
            f"hoy" if dias == 0 else
            f"en {dias} día(s)" if dias > 0 else
            f"vencido hace {-dias} día(s)"
        )
        filas.append([
            c.fecha_deposito.strftime('%d/%m/%Y') if c.fecha_deposito else '—',
            cuando,
            c.banco_emision or '—',
            c.numero_cheque or '—',
            c.titular_cheque or '—',
            c.cliente or '—',
            f"$ {(c.monto or 0):,.0f}".replace(',', '.'),
        ])

    totales = ['', '', '', '', '', 'TOTAL',
               f"$ {total:,.0f}".replace(',', '.')]

    return render_pdf_listado(
        filename=f"cheques_a_cobrar_{hoy.strftime('%Y%m%d')}.pdf",
        titulo="Cheques a Cobrar",
        subtitulo=f"Listado al {hoy.strftime('%d/%m/%Y')} – {len(filas)} cheque(s) pendientes",
        columnas=['Fecha cobro', 'Cuándo', 'Banco', 'Nº cheque', 'Titular', 'Cliente', 'Monto'],
        filas=filas,
        totales=totales if filas else None,
        pie="Estado: A depositar",
    )
