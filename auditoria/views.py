from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.db import transaction
from django.core.paginator import Paginator
from django.apps import apps

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


# ==========================================================
# RECUPERAR REGISTROS ELIMINADOS DESDE AUDITORÍA
# ==========================================================
def _buscar_modelo(nombre_clase: str):
    """Busca el modelo por nombre de clase, aunque no sepamos el app_label."""
    nombre_lower = nombre_clase.lower()
    for Model in apps.get_models():
        if Model.__name__.lower() == nombre_lower:
            return Model
    return None


@login_required
@user_passes_test(_es_admin, login_url="inicio")
def lista_eliminados(request):
    logs = (
        LogActividad.objects
        .filter(accion="eliminar")
        .exclude(datos_antes__isnull=True)
        .select_related("usuario")
        .order_by("-fecha")
    )

    modelo_filtro = request.GET.get("modelo", "")
    if modelo_filtro:
        logs = logs.filter(modelo=modelo_filtro)

    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    modelos_choices = (
        LogActividad.objects
        .filter(accion="eliminar")
        .values_list("modelo", flat=True)
        .exclude(modelo="")
        .distinct()
        .order_by("modelo")
    )

    return render(request, "auditoria/lista_eliminados.html", {
        "page_obj": page_obj,
        "logs": page_obj.object_list,
        "total": paginator.count,
        "modelo_filtro": modelo_filtro,
        "modelos_choices": modelos_choices,
    })


@login_required
@user_passes_test(_es_admin, login_url="inicio")
@transaction.atomic
def restaurar_registro(request, log_id):
    log = get_object_or_404(LogActividad, id=log_id, accion="eliminar")

    if not log.datos_antes:
        messages.error(request, "Este log no tiene snapshot para restaurar.")
        return redirect("auditoria:lista_eliminados")

    Model = _buscar_modelo(log.modelo)
    if not Model:
        messages.error(
            request,
            f"No encuentro el modelo \"{log.modelo}\". Tal vez fue renombrado."
        )
        return redirect("auditoria:lista_eliminados")

    if request.method != "POST":
        return redirect("auditoria:lista_eliminados")

    # Si el ID original sigue libre, lo reusamos. Si no, dejamos que la base
    # genere uno nuevo (puede romper FKs apuntando al ID viejo, pero el
    # registro queda recuperado).
    pk_original = log.objeto_id or log.datos_antes.get("id")
    if pk_original and Model.objects.filter(pk=pk_original).exists():
        messages.warning(
            request,
            f"Ya existe un registro con id={pk_original}. "
            "Se creó una copia con id nuevo."
        )
        usar_pk_original = False
    else:
        usar_pk_original = bool(pk_original)

    # Reconstruir objeto a partir del snapshot. Para FKs guardamos solo el ID
    # en datos_antes, pero la columna en BD termina en "_id".
    field_names = {f.name for f in Model._meta.fields}
    fk_names = {f.name for f in Model._meta.fields if f.is_relation}

    init_kwargs = {}
    for campo, valor in log.datos_antes.items():
        if campo == "id":
            continue
        if campo in fk_names:
            init_kwargs[f"{campo}_id"] = valor
        elif campo in field_names:
            init_kwargs[campo] = valor

    if usar_pk_original:
        init_kwargs["id"] = pk_original

    try:
        instancia = Model(**init_kwargs)
        instancia.save()
    except Exception as e:
        messages.error(
            request,
            f"No se pudo restaurar el registro: {type(e).__name__}: {e}"
        )
        return redirect("auditoria:lista_eliminados")

    messages.success(
        request,
        f"Restaurado: {Model.__name__} #{instancia.pk} — {instancia}"
    )
    return redirect("auditoria:lista_eliminados")
