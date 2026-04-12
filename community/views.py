from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

from vehiculos.models import Vehiculo
from .models import FotoVehiculo, PublicacionPlataforma


# ==========================================================
# DASHBOARD COMMUNITY
# ==========================================================
@login_required
def community_dashboard(request):
    vehiculos = Vehiculo.objects.filter(estado="stock").order_by("-id")

    q = request.GET.get("q", "").strip()
    if q:
        vehiculos = vehiculos.filter(
            Q(marca__icontains=q) |
            Q(modelo__icontains=q) |
            Q(dominio__icontains=q)
        )

    filtro = request.GET.get("filtro", "")

    vehiculos_data = []
    total_sin_fotos = 0
    total_sin_publicar = 0
    total_completos = 0

    for v in vehiculos:
        fotos_count = v.fotos.count()
        pubs = {p.plataforma: p.publicado for p in v.publicaciones.all()}
        plataformas_publicadas = sum(1 for val in pubs.values() if val)
        todas_publicadas = plataformas_publicadas == 4
        portada = v.fotos.filter(es_portada=True).first()

        if fotos_count == 0:
            total_sin_fotos += 1
        if not todas_publicadas:
            total_sin_publicar += 1
        if fotos_count > 0 and todas_publicadas:
            total_completos += 1

        PLAT_KEYS = ["mercadolibre", "facebook", "instagram", "web"]
        plataformas_list = [
            {"key": k, "publicado": pubs.get(k, False)}
            for k in PLAT_KEYS
        ]

        item = {
            "vehiculo": v,
            "fotos_count": fotos_count,
            "portada": portada,
            "pubs": pubs,
            "plataformas_list": plataformas_list,
            "plataformas_publicadas": plataformas_publicadas,
            "todas_publicadas": todas_publicadas,
        }

        if filtro == "sin_fotos" and fotos_count > 0:
            continue
        if filtro == "sin_publicar" and todas_publicadas:
            continue
        if filtro == "completo" and not (fotos_count > 0 and todas_publicadas):
            continue

        vehiculos_data.append(item)

    return render(request, "community/dashboard.html", {
        "vehiculos_data": vehiculos_data,
        "query": q,
        "filtro": filtro,
        "total_stock": vehiculos.count(),
        "total_sin_fotos": total_sin_fotos,
        "total_sin_publicar": total_sin_publicar,
        "total_completos": total_completos,
    })


# ==========================================================
# FOTOS DE UN VEHÍCULO
# ==========================================================
@login_required
def vehiculo_fotos(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    fotos = vehiculo.fotos.all()

    for key, label in PublicacionPlataforma.PLATAFORMAS:
        PublicacionPlataforma.objects.get_or_create(
            vehiculo=vehiculo, plataforma=key
        )
    publicaciones = vehiculo.publicaciones.all()

    if request.method == "POST":
        imagenes = request.FILES.getlist("imagenes")
        for img in imagenes:
            es_primera = not vehiculo.fotos.exists()
            FotoVehiculo.objects.create(
                vehiculo=vehiculo,
                imagen=img,
                es_portada=es_primera,
            )
        messages.success(request, f"{len(imagenes)} foto(s) subida(s).")
        return redirect("community:vehiculo_fotos", vehiculo_id=vehiculo.id)

    return render(request, "community/vehiculo_fotos.html", {
        "vehiculo": vehiculo,
        "fotos": fotos,
        "publicaciones": publicaciones,
    })


# ==========================================================
# ELIMINAR FOTO
# ==========================================================
@login_required
def eliminar_foto(request, foto_id):
    foto = get_object_or_404(FotoVehiculo, id=foto_id)
    vehiculo_id = foto.vehiculo_id
    foto.imagen.delete(save=False)
    foto.delete()
    messages.success(request, "Foto eliminada.")
    return redirect("community:vehiculo_fotos", vehiculo_id=vehiculo_id)


# ==========================================================
# MARCAR FOTO COMO PORTADA
# ==========================================================
@login_required
def marcar_portada(request, foto_id):
    foto = get_object_or_404(FotoVehiculo, id=foto_id)
    foto.es_portada = True
    foto.save()
    return redirect("community:vehiculo_fotos", vehiculo_id=foto.vehiculo_id)


# ==========================================================
# TOGGLE PUBLICACIÓN EN PLATAFORMA (AJAX)
# ==========================================================
@csrf_exempt
@login_required
def toggle_publicacion(request, vehiculo_id, plataforma):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    pub, _ = PublicacionPlataforma.objects.get_or_create(
        vehiculo=vehiculo, plataforma=plataforma
    )
    pub.publicado = not pub.publicado
    if pub.publicado:
        from datetime import date
        pub.fecha_publicacion = date.today()
    else:
        pub.fecha_publicacion = None
    pub.save()
    return JsonResponse({"ok": True, "publicado": pub.publicado})


# ==========================================================
# CATÁLOGO PÚBLICO (SIN LOGIN, SIN PRECIO)
# ==========================================================
def catalogo_publico(request):
    vehiculos = Vehiculo.objects.filter(estado="stock").order_by("marca", "modelo")

    catalogo = []
    for v in vehiculos:
        portada = v.fotos.filter(es_portada=True).first()
        fotos = v.fotos.all()
        if fotos.exists():
            catalogo.append({
                "vehiculo": v,
                "portada": portada or fotos.first(),
                "fotos": fotos,
            })

    return render(request, "community/catalogo_publico.html", {
        "catalogo": catalogo,
        "total": len(catalogo),
    })
