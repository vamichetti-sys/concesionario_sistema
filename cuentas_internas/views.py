from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum

from .models import CuentaInterna, MovimientoInterno
from .forms import CuentaInternaForm, MovimientoInternoForm


def usuario_autorizado(user):
    return user.username in ['Vamichetti', 'Hamichetti']


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