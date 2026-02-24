from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from .models import Presupuesto
from .forms import PresupuestoForm


@login_required
def lista_presupuestos(request):
    query = request.GET.get('q', '')
    estado_filtro = request.GET.get('estado', '')

    presupuestos = Presupuesto.objects.select_related('vehiculo', 'cliente', 'vendedor').all()

    if query:
        presupuestos = presupuestos.filter(
            Q(nombre_cliente__icontains=query) |
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query)
        )

    if estado_filtro:
        presupuestos = presupuestos.filter(estado=estado_filtro)

    # Contadores
    total = Presupuesto.objects.count()
    borradores = Presupuesto.objects.filter(estado='borrador').count()
    enviados = Presupuesto.objects.filter(estado='enviado').count()
    aceptados = Presupuesto.objects.filter(estado='aceptado').count()

    return render(request, 'presupuestos/lista.html', {
        'presupuestos': presupuestos,
        'query': query,
        'estado_filtro': estado_filtro,
        'total': total,
        'borradores': borradores,
        'enviados': enviados,
        'aceptados': aceptados,
    })


@login_required
def crear_presupuesto(request):
    if request.method == 'POST':
        form = PresupuestoForm(request.POST)
        if form.is_valid():
            presupuesto = form.save(commit=False)
            
            # Auto-numerar
            ultimo = Presupuesto.objects.order_by('-numero').first()
            presupuesto.numero = (ultimo.numero + 1) if ultimo else 1
            presupuesto.vendedor = request.user
            presupuesto.save()
            
            messages.success(request, f'Presupuesto #{presupuesto.numero} creado.')
            return redirect('presupuestos:detalle', pk=presupuesto.pk)
    else:
        form = PresupuestoForm()

    return render(request, 'presupuestos/form.html', {
        'form': form,
        'titulo': 'Nuevo Presupuesto',
    })


@login_required
def detalle_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    return render(request, 'presupuestos/detalle.html', {
        'p': presupuesto,
    })


@login_required
def editar_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)

    if request.method == 'POST':
        form = PresupuestoForm(request.POST, instance=presupuesto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Presupuesto actualizado.')
            return redirect('presupuestos:detalle', pk=presupuesto.pk)
    else:
        form = PresupuestoForm(instance=presupuesto)

    return render(request, 'presupuestos/form.html', {
        'form': form,
        'titulo': f'Editar Presupuesto #{presupuesto.numero}',
        'presupuesto': presupuesto,
    })


@login_required
def eliminar_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)

    if request.method == 'POST':
        numero = presupuesto.numero
        presupuesto.delete()
        messages.success(request, f'Presupuesto #{numero} eliminado.')
        return redirect('presupuestos:lista')

    return render(request, 'presupuestos/eliminar.html', {
        'presupuesto': presupuesto,
    })


@login_required
def marcar_enviado(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    presupuesto.estado = 'enviado'
    presupuesto.fecha_envio = timezone.now()
    presupuesto.save(update_fields=['estado', 'fecha_envio'])
    messages.success(request, f'Presupuesto #{presupuesto.numero} marcado como enviado.')
    return redirect('presupuestos:detalle', pk=presupuesto.pk)


@login_required
def cambiar_estado(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['borrador', 'enviado', 'aceptado', 'rechazado', 'vencido']:
            presupuesto.estado = nuevo_estado
            if nuevo_estado == 'enviado' and not presupuesto.fecha_envio:
                presupuesto.fecha_envio = timezone.now()
            presupuesto.save()
            messages.success(request, f'Estado actualizado a {nuevo_estado}.')
    
    return redirect('presupuestos:detalle', pk=presupuesto.pk)