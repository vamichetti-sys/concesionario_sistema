from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from datetime import date, timedelta

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
def cambiar_estado_cheque(request, pk):
    if not usuario_autorizado(request.user):
        messages.error(request, 'No tenés permiso para acceder a esta sección.')
        return redirect('inicio')
    
    cheque = get_object_or_404(Cheque, pk=pk)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        depositado_en = request.POST.get('depositado_en', '')
        fecha_endoso = request.POST.get('fecha_endoso', '')
        destinatario_endoso = request.POST.get('destinatario_endoso', '')
        
        if nuevo_estado in ['a_depositar', 'depositado', 'endosado', 'rechazado']:
            cheque.estado = nuevo_estado
            
            if nuevo_estado == 'depositado':
                cheque.depositado_en = depositado_en
            elif nuevo_estado == 'endosado':
                if fecha_endoso:
                    cheque.fecha_endoso = fecha_endoso
                cheque.destinatario_endoso = destinatario_endoso
            
            cheque.save()
            messages.success(request, f'Estado actualizado a {cheque.get_estado_display()}.')
    
    return redirect('cheques:lista')