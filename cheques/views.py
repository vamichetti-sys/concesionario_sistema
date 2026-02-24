from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from datetime import date

from .models import Cheque
from .forms import ChequeForm


def usuario_autorizado(user):
    return user.username in ['Vamichetti', 'Hamichetti']


@login_required
def lista_cheques(request):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    query = request.GET.get('q', '')
    tipo_filtro = request.GET.get('tipo', '')
    estado_filtro = request.GET.get('estado', '')
    
    cheques = Cheque.objects.all()
    
    if query:
        cheques = cheques.filter(
            Q(numero__icontains=query) |
            Q(titular__icontains=query) |
            Q(banco__icontains=query) |
            Q(origen_destino__icontains=query)
        )
    
    if tipo_filtro:
        cheques = cheques.filter(tipo=tipo_filtro)
    
    if estado_filtro:
        cheques = cheques.filter(estado=estado_filtro)
    
    # Totales
    total_recibidos = Cheque.objects.filter(tipo='recibido', estado='cartera').aggregate(Sum('monto'))['monto__sum'] or 0
    total_emitidos = Cheque.objects.filter(tipo='emitido', estado='cartera').aggregate(Sum('monto'))['monto__sum'] or 0
    proximos_cobro = Cheque.objects.filter(estado='cartera', fecha_cobro__lte=date.today()).count()
    
    return render(request, 'cheques/lista.html', {
        'cheques': cheques,
        'query': query,
        'tipo_filtro': tipo_filtro,
        'estado_filtro': estado_filtro,
        'total_recibidos': total_recibidos,
        'total_emitidos': total_emitidos,
        'proximos_cobro': proximos_cobro,
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
            messages.success(request, f'Cheque #{cheque.numero} creado.')
            return redirect('cheques:lista')
    else:
        form = ChequeForm()
    
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
        'titulo': f'Editar Cheque #{cheque.numero}',
        'cheque': cheque,
    })


@login_required
def eliminar_cheque(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cheque = get_object_or_404(Cheque, pk=pk)
    
    if request.method == 'POST':
        numero = cheque.numero
        cheque.delete()
        messages.success(request, f'Cheque #{numero} eliminado.')
        return redirect('cheques:lista')
    
    return render(request, 'cheques/eliminar.html', {'cheque': cheque})


@login_required
def cambiar_estado_cheque(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cheque = get_object_or_404(Cheque, pk=pk)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['cartera', 'depositado', 'cobrado', 'entregado', 'rechazado', 'vencido']:
            cheque.estado = nuevo_estado
            cheque.save()
            messages.success(request, f'Estado actualizado a {cheque.get_estado_display()}.')
    
    return redirect('cheques:lista')