from datetime import timedelta, datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q

from .models import Proyecto, Tarea, Recordatorio, TareaDiaria
from .forms import ProyectoForm, TareaForm, RecordatorioForm
from .decorators import solo_usuario_principal


# ==========================================================
# DASHBOARD
# ==========================================================
@solo_usuario_principal
def dashboard(request):
    ahora = timezone.now()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    semana_fin = hoy_inicio + timedelta(days=7)
    proximas_48 = ahora + timedelta(hours=48)

    qs_tareas = Tarea.objects.filter(usuario=request.user).select_related('proyecto')

    proyectos_activos = (
        Proyecto.objects
        .filter(usuario=request.user, activo=True)
        .prefetch_related('tareas')
    )

    tareas_hoy = qs_tareas.filter(
        deadline__gte=hoy_inicio,
        deadline__lt=hoy_fin,
    ).exclude(estado='hecha')

    tareas_semana = qs_tareas.filter(
        deadline__gte=hoy_fin,
        deadline__lt=semana_fin,
    ).exclude(estado='hecha')

    tareas_vencidas = qs_tareas.filter(
        deadline__lt=ahora,
    ).exclude(estado='hecha')

    recordatorios_proximos = (
        Recordatorio.objects
        .filter(
            usuario=request.user,
            fecha_hora__gte=ahora,
            fecha_hora__lte=proximas_48,
        )
        .select_related('tarea')
    )

    # Métricas para las cards superiores
    metricas = {
        'total_proyectos': proyectos_activos.count(),
        'total_tareas_pend': qs_tareas.exclude(estado='hecha').count(),
        'total_vencidas': tareas_vencidas.count(),
        'total_recordatorios': recordatorios_proximos.count(),
    }

    contexto = {
        'page_title': 'Proyectos - Dashboard',
        'proyectos_activos': proyectos_activos,
        'tareas_hoy': tareas_hoy,
        'tareas_semana': tareas_semana,
        'tareas_vencidas': tareas_vencidas,
        'recordatorios_proximos': recordatorios_proximos,
        'metricas': metricas,
    }
    return render(request, 'proyectos/dashboard.html', contexto)


# ==========================================================
# PROYECTOS - CRUD
# ==========================================================
@solo_usuario_principal
def proyecto_lista(request):
    proyectos = Proyecto.objects.filter(usuario=request.user)
    return render(request, 'proyectos/proyecto_lista.html', {
        'page_title': 'Mis Proyectos',
        'proyectos': proyectos,
    })


@solo_usuario_principal
def proyecto_crear(request):
    if request.method == 'POST':
        form = ProyectoForm(request.POST)
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.usuario = request.user
            proyecto.save()
            messages.success(request, 'Proyecto creado.')
            return redirect('proyectos:proyecto_detail', pk=proyecto.pk)
    else:
        form = ProyectoForm()
    return render(request, 'proyectos/proyecto_form.html', {
        'page_title': 'Nuevo proyecto',
        'form': form,
        'modo': 'crear',
    })


@solo_usuario_principal
def proyecto_editar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk, usuario=request.user)
    if request.method == 'POST':
        form = ProyectoForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proyecto actualizado.')
            return redirect('proyectos:proyecto_detail', pk=proyecto.pk)
    else:
        form = ProyectoForm(instance=proyecto)
    return render(request, 'proyectos/proyecto_form.html', {
        'page_title': f'Editar: {proyecto.nombre}',
        'form': form,
        'modo': 'editar',
        'proyecto': proyecto,
    })


@solo_usuario_principal
def proyecto_eliminar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk, usuario=request.user)
    if request.method == 'POST':
        proyecto.delete()
        messages.success(request, 'Proyecto eliminado.')
        return redirect('proyectos:proyecto_lista')
    return redirect('proyectos:proyecto_detail', pk=pk)


@solo_usuario_principal
def proyecto_detail(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk, usuario=request.user)
    tareas = proyecto.tareas.all()

    # Agrupamos por estado para mostrar columnas / secciones en el detalle
    tareas_por_estado = {
        'pend': tareas.filter(estado='pend'),
        'curso': tareas.filter(estado='curso'),
        'bloq': tareas.filter(estado='bloq'),
        'hecha': tareas.filter(estado='hecha'),
    }

    return render(request, 'proyectos/proyecto_detail.html', {
        'page_title': proyecto.nombre,
        'proyecto': proyecto,
        'tareas_por_estado': tareas_por_estado,
    })


# ==========================================================
# TAREAS
# ==========================================================
@solo_usuario_principal
def tarea_lista(request):
    qs = Tarea.objects.filter(usuario=request.user).select_related('proyecto')

    # Filtros desde querystring
    f_proyecto = request.GET.get('proyecto', '').strip()
    f_estado = request.GET.get('estado', '').strip()
    f_prioridad = request.GET.get('prioridad', '').strip()
    f_buscar = request.GET.get('q', '').strip()

    if f_proyecto:
        qs = qs.filter(proyecto_id=f_proyecto)
    if f_estado:
        qs = qs.filter(estado=f_estado)
    if f_prioridad:
        qs = qs.filter(prioridad=f_prioridad)
    if f_buscar:
        qs = qs.filter(
            Q(titulo__icontains=f_buscar) | Q(descripcion__icontains=f_buscar)
        )

    proyectos = Proyecto.objects.filter(usuario=request.user)

    return render(request, 'proyectos/tareas_lista.html', {
        'page_title': 'Tareas',
        'tareas': qs,
        'proyectos': proyectos,
        'filtros': {
            'proyecto': f_proyecto,
            'estado': f_estado,
            'prioridad': f_prioridad,
            'q': f_buscar,
        },
        'estados': Tarea.ESTADO_CHOICES,
        'prioridades': Tarea.PRIORIDAD_CHOICES,
    })


@solo_usuario_principal
def tarea_crear(request):
    if request.method == 'POST':
        form = TareaForm(request.POST, user=request.user)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.usuario = request.user
            tarea.save()
            messages.success(request, 'Tarea creada.')
            return redirect('proyectos:tarea_lista')
    else:
        # Permite preseleccionar proyecto vía ?proyecto=<id>
        initial = {}
        proyecto_id = request.GET.get('proyecto')
        if proyecto_id:
            initial['proyecto'] = proyecto_id
        form = TareaForm(user=request.user, initial=initial)
    return render(request, 'proyectos/tarea_form.html', {
        'page_title': 'Nueva tarea',
        'form': form,
        'modo': 'crear',
    })


@solo_usuario_principal
def tarea_editar(request, pk):
    tarea = get_object_or_404(Tarea, pk=pk, usuario=request.user)
    if request.method == 'POST':
        form = TareaForm(request.POST, instance=tarea, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tarea actualizada.')
            return redirect('proyectos:tarea_lista')
    else:
        form = TareaForm(instance=tarea, user=request.user)
    return render(request, 'proyectos/tarea_form.html', {
        'page_title': f'Editar: {tarea.titulo}',
        'form': form,
        'modo': 'editar',
        'tarea': tarea,
    })


@solo_usuario_principal
def tarea_eliminar(request, pk):
    tarea = get_object_or_404(Tarea, pk=pk, usuario=request.user)
    if request.method == 'POST':
        tarea.delete()
        messages.success(request, 'Tarea eliminada.')
    return redirect('proyectos:tarea_lista')


@solo_usuario_principal
@require_POST
def tarea_cambiar_estado(request, pk):
    """
    Endpoint AJAX para cambiar rápidamente el estado de una tarea
    desde el dashboard o el detalle del proyecto.
    """
    tarea = get_object_or_404(Tarea, pk=pk, usuario=request.user)
    nuevo_estado = request.POST.get('estado', '').strip()
    estados_validos = {key for key, _ in Tarea.ESTADO_CHOICES}
    if nuevo_estado not in estados_validos:
        return HttpResponseBadRequest('Estado inválido.')

    tarea.estado = nuevo_estado
    tarea.save()
    return JsonResponse({
        'ok': True,
        'estado': tarea.estado,
        'estado_label': tarea.get_estado_display(),
        'completada_en': tarea.completada_en.isoformat() if tarea.completada_en else None,
    })


# ==========================================================
# CALENDARIO
# ==========================================================
@solo_usuario_principal
def calendario(request):
    return render(request, 'proyectos/calendario.html', {
        'page_title': 'Calendario',
    })


@solo_usuario_principal
def calendario_eventos_json(request):
    """
    Feed de eventos para FullCalendar.io. Incluye tareas con deadline y
    recordatorios. Cada evento se colorea con el color de su proyecto
    (o un color neutro para los recordatorios sueltos).
    """
    eventos = []

    tareas = (
        Tarea.objects
        .filter(usuario=request.user, deadline__isnull=False)
        .select_related('proyecto')
    )
    for t in tareas:
        eventos.append({
            'id': f'tarea-{t.pk}',
            'title': t.titulo,
            'start': t.deadline.isoformat(),
            'color': t.proyecto.color,
            'url': '',
            'extendedProps': {
                'tipo': 'tarea',
                'estado': t.get_estado_display(),
                'prioridad': t.get_prioridad_display(),
                'proyecto': t.proyecto.nombre,
            },
        })

    recordatorios = (
        Recordatorio.objects
        .filter(usuario=request.user)
        .select_related('tarea__proyecto')
    )
    for r in recordatorios:
        color = '#6b7280'
        if r.tarea and r.tarea.proyecto:
            color = r.tarea.proyecto.color
        eventos.append({
            'id': f'recordatorio-{r.pk}',
            'title': f'🔔 {r.titulo}',
            'start': r.fecha_hora.isoformat(),
            'color': color,
            'extendedProps': {
                'tipo': 'recordatorio',
                'notificado': r.notificado,
            },
        })

    return JsonResponse(eventos, safe=False)


# ==========================================================
# RECORDATORIOS
# ==========================================================
@solo_usuario_principal
def recordatorio_lista(request):
    if request.method == 'POST':
        form = RecordatorioForm(request.POST, user=request.user)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.usuario = request.user
            rec.save()
            messages.success(request, 'Recordatorio creado.')
            return redirect('proyectos:recordatorio_lista')
    else:
        form = RecordatorioForm(user=request.user)

    recordatorios = (
        Recordatorio.objects
        .filter(usuario=request.user)
        .select_related('tarea')
    )
    return render(request, 'proyectos/recordatorios_lista.html', {
        'page_title': 'Recordatorios',
        'recordatorios': recordatorios,
        'form': form,
    })


@solo_usuario_principal
def recordatorio_editar(request, pk):
    rec = get_object_or_404(Recordatorio, pk=pk, usuario=request.user)
    if request.method == 'POST':
        form = RecordatorioForm(request.POST, instance=rec, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Recordatorio actualizado.')
            return redirect('proyectos:recordatorio_lista')
    else:
        form = RecordatorioForm(instance=rec, user=request.user)
    # Reutilizamos la misma plantilla, pasando el form con instancia
    return render(request, 'proyectos/recordatorios_lista.html', {
        'page_title': 'Editar recordatorio',
        'recordatorios': Recordatorio.objects.filter(usuario=request.user),
        'form': form,
        'editando': rec,
    })


@solo_usuario_principal
def recordatorio_eliminar(request, pk):
    rec = get_object_or_404(Recordatorio, pk=pk, usuario=request.user)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Recordatorio eliminado.')
    return redirect('proyectos:recordatorio_lista')


# ==========================================================
# API: recordatorios pendientes (para mostrar en el navbar)
# ==========================================================
@solo_usuario_principal
def api_recordatorios_pendientes(request):
    """
    Devuelve los recordatorios cuya fecha_hora <= ahora y que aún no
    fueron marcados como notificados. Usado para badge/aviso en el navbar.
    """
    ahora = timezone.now()
    pendientes = (
        Recordatorio.objects
        .filter(
            usuario=request.user,
            notificado=False,
            fecha_hora__lte=ahora,
        )
        .select_related('tarea')
    )
    data = [{
        'id': r.pk,
        'titulo': r.titulo,
        'fecha_hora': r.fecha_hora.isoformat(),
        'tarea': r.tarea.titulo if r.tarea else None,
    } for r in pendientes]
    return JsonResponse({'count': len(data), 'recordatorios': data})


# ==========================================================
# AGENDA DIARIA — to-do simple por día
# ==========================================================
def _parse_fecha(valor):
    """Devuelve la fecha del querystring (YYYY-MM-DD) o hoy si es inválida."""
    if valor:
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    return timezone.localdate()


@solo_usuario_principal
def agenda_diaria(request):
    fecha = _parse_fecha(request.GET.get('fecha'))
    hoy = timezone.localdate()

    tareas = TareaDiaria.objects.filter(usuario=request.user, fecha=fecha)

    # Pendientes arrastradas de días anteriores (solo si miramos hoy o el futuro)
    atrasadas = []
    if fecha >= hoy:
        atrasadas = (
            TareaDiaria.objects
            .filter(usuario=request.user, hecha=False, fecha__lt=hoy)
            .order_by('fecha', 'hora', 'orden')
        )

    total = tareas.count()
    hechas = tareas.filter(hecha=True).count()
    progreso = int(round((hechas / total) * 100)) if total else 0

    return render(request, 'proyectos/agenda_diaria.html', {
        'fecha': fecha,
        'hoy': hoy,
        'dia_anterior': fecha - timedelta(days=1),
        'dia_siguiente': fecha + timedelta(days=1),
        'tareas': tareas,
        'atrasadas': atrasadas,
        'total': total,
        'hechas': hechas,
        'pendientes': total - hechas,
        'progreso': progreso,
        'prioridades': TareaDiaria.PRIORIDAD_CHOICES,
    })


@solo_usuario_principal
@require_POST
def agenda_diaria_agregar(request):
    fecha = _parse_fecha(request.POST.get('fecha'))
    texto = (request.POST.get('texto') or '').strip()
    if not texto:
        messages.error(request, 'Escribí la tarea.')
        return redirect(f"{request.path_info}")

    prioridad = request.POST.get('prioridad') or 'media'
    if prioridad not in dict(TareaDiaria.PRIORIDAD_CHOICES):
        prioridad = 'media'

    hora = None
    hora_str = (request.POST.get('hora') or '').strip()
    if hora_str:
        try:
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            hora = None

    TareaDiaria.objects.create(
        usuario=request.user,
        fecha=fecha,
        texto=texto[:300],
        prioridad=prioridad,
        hora=hora,
    )
    messages.success(request, 'Tarea agregada.')
    return redirect(f"{reverse('proyectos:agenda_diaria')}?fecha={fecha:%Y-%m-%d}")


@solo_usuario_principal
@require_POST
def agenda_diaria_toggle(request, pk):
    t = get_object_or_404(TareaDiaria, pk=pk, usuario=request.user)
    t.hecha = not t.hecha
    t.save()
    return redirect(f"{reverse('proyectos:agenda_diaria')}?fecha={t.fecha:%Y-%m-%d}")


@solo_usuario_principal
@require_POST
def agenda_diaria_editar(request, pk):
    t = get_object_or_404(TareaDiaria, pk=pk, usuario=request.user)
    texto = (request.POST.get('texto') or '').strip()
    if texto:
        t.texto = texto[:300]
    prioridad = request.POST.get('prioridad')
    if prioridad in dict(TareaDiaria.PRIORIDAD_CHOICES):
        t.prioridad = prioridad
    hora_str = (request.POST.get('hora') or '').strip()
    if hora_str:
        try:
            t.hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            pass
    else:
        t.hora = None
    t.save()
    messages.success(request, 'Tarea actualizada.')
    return redirect(f"{reverse('proyectos:agenda_diaria')}?fecha={t.fecha:%Y-%m-%d}")


@solo_usuario_principal
@require_POST
def agenda_diaria_eliminar(request, pk):
    t = get_object_or_404(TareaDiaria, pk=pk, usuario=request.user)
    fecha = t.fecha
    t.delete()
    messages.success(request, 'Tarea eliminada.')
    return redirect(f"{reverse('proyectos:agenda_diaria')}?fecha={fecha:%Y-%m-%d}")


@solo_usuario_principal
@require_POST
def agenda_diaria_mover_hoy(request, pk):
    """Pasa una tarea atrasada al día de hoy."""
    t = get_object_or_404(TareaDiaria, pk=pk, usuario=request.user)
    t.fecha = timezone.localdate()
    t.save()
    messages.success(request, 'Tarea movida a hoy.')
    return redirect('proyectos:agenda_diaria')
