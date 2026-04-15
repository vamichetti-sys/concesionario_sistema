from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.core.paginator import Paginator

from .models import LogActividad


def _es_admin(user):
    return user.is_superuser or user.username in ("Vamichetti", "Hamichetti")


@login_required
@user_passes_test(_es_admin, login_url="inicio")
def lista_logs(request):
    logs = LogActividad.objects.select_related("usuario").all()

    # Filtros
    q = request.GET.get("q", "").strip()
    accion = request.GET.get("accion", "")
    modelo = request.GET.get("modelo", "")
    usuario = request.GET.get("usuario", "")
    fecha_desde = request.GET.get("desde", "")
    fecha_hasta = request.GET.get("hasta", "")

    if q:
        logs = logs.filter(
            Q(descripcion__icontains=q) |
            Q(usuario_texto__icontains=q) |
            Q(modelo__icontains=q) |
            Q(objeto_id__icontains=q)
        )
    if accion:
        logs = logs.filter(accion=accion)
    if modelo:
        logs = logs.filter(modelo=modelo)
    if usuario:
        logs = logs.filter(usuario_texto__icontains=usuario)
    if fecha_desde:
        logs = logs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        logs = logs.filter(fecha__date__lte=fecha_hasta)

    # Paginación
    paginator = Paginator(logs, 50)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Opciones de filtro
    modelos_choices = (
        LogActividad.objects.values_list("modelo", flat=True)
        .exclude(modelo="")
        .distinct()
        .order_by("modelo")
    )

    return render(request, "auditoria/lista_logs.html", {
        "page_obj": page_obj,
        "logs": page_obj.object_list,
        "total": paginator.count,
        "query": q,
        "accion": accion,
        "modelo": modelo,
        "usuario": usuario,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "acciones_choices": LogActividad.ACCIONES,
        "modelos_choices": modelos_choices,
    })
