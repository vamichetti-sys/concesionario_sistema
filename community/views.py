from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from datetime import date
from io import BytesIO
import urllib.request

from PIL import Image as PILImage, ImageOps

from vehiculos.models import Vehiculo
from .models import FotoVehiculo, PublicacionPlataforma


MAX_SIZE_PX = 2000          # lado máximo en píxeles
JPEG_QUALITY = 82           # calidad de compresión
MAX_BYTES_CLOUDINARY = 9_500_000  # dejar margen sobre el límite de 10 MB


def comprimir_imagen(img_file):
    """
    Redimensiona y comprime una imagen para que pese menos de 10 MB.
    Mantiene la orientación EXIF y convierte a JPEG optimizado.
    """
    try:
        pil_img = PILImage.open(img_file)
        pil_img = ImageOps.exif_transpose(pil_img)

        if pil_img.mode not in ("RGB", "L"):
            pil_img = pil_img.convert("RGB")

        # Redimensionar si excede tamaño máximo
        pil_img.thumbnail((MAX_SIZE_PX, MAX_SIZE_PX), PILImage.LANCZOS)

        # Comprimir progresivamente si sigue pesando mucho
        calidad = JPEG_QUALITY
        buffer = BytesIO()
        pil_img.save(buffer, format="JPEG", quality=calidad, optimize=True)

        while buffer.tell() > MAX_BYTES_CLOUDINARY and calidad > 40:
            calidad -= 10
            buffer = BytesIO()
            pil_img.save(buffer, format="JPEG", quality=calidad, optimize=True)

        buffer.seek(0)
        nombre = img_file.name.rsplit(".", 1)[0] + ".jpg"
        return InMemoryUploadedFile(
            buffer, None, nombre, "image/jpeg",
            buffer.getbuffer().nbytes, None
        )
    except Exception:
        img_file.seek(0)
        return img_file

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm


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
        exitosas = 0
        fallidas = []
        for img in imagenes:
            try:
                img_comprimida = comprimir_imagen(img)
                es_primera = not vehiculo.fotos.exists()
                FotoVehiculo.objects.create(
                    vehiculo=vehiculo,
                    imagen=img_comprimida,
                    es_portada=es_primera,
                )
                exitosas += 1
            except Exception as e:
                fallidas.append(f"{img.name}: {e}")

        if exitosas:
            messages.success(request, f"{exitosas} foto(s) subida(s).")
        if fallidas:
            messages.error(request, "No se pudieron subir: " + "; ".join(fallidas))

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
        fotos = list(v.fotos.all())
        if fotos:
            portada = next((f for f in fotos if f.es_portada), fotos[0])
            catalogo.append({
                "vehiculo": v,
                "portada": portada,
                "fotos_list": fotos,
            })

    return render(request, "community/catalogo_publico.html", {
        "catalogo": catalogo,
        "total": len(catalogo),
    })


# ==========================================================
# PDF CATÁLOGO (SIN PRECIO)
# ==========================================================
def catalogo_pdf(request):
    vehiculos = Vehiculo.objects.filter(
        estado__in=["stock", "temporal"]
    ).order_by("marca", "modelo")

    hoy = date.today()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30,
    )

    AZUL = colors.HexColor("#002855")
    GRIS = colors.HexColor("#F4F6F8")

    elementos = []

    # Header
    header = Table([[
        Paragraph(
            "<b>AMICHETTI AUTOMOTORES</b><br/>Catálogo de vehículos en stock",
            ParagraphStyle("h1", fontSize=14, textColor=colors.white)
        ),
        Paragraph(
            f"Fecha: {hoy.strftime('%d/%m/%Y')}",
            ParagraphStyle("h2", fontSize=10, textColor=colors.white, alignment=2)
        ),
    ]], colWidths=[340, 180])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("PADDING", (0, 0), (-1, -1), 14),
    ]))
    elementos.append(header)
    elementos.append(Spacer(1, 16))

    # Recorrer vehículos de a 2 por fila
    vehiculos_con_foto = []
    for v in vehiculos:
        portada = v.fotos.filter(es_portada=True).first() or v.fotos.first()
        vehiculos_con_foto.append((v, portada))

    estilo_titulo = ParagraphStyle("t", fontSize=11, fontName="Helvetica-Bold", leading=13)
    estilo_dato = ParagraphStyle("d", fontSize=9, textColor=colors.HexColor("#555555"), leading=11)

    for i in range(0, len(vehiculos_con_foto), 2):
        celdas = []
        for j in range(2):
            idx = i + j
            if idx >= len(vehiculos_con_foto):
                celdas.append("")
                continue

            v, portada = vehiculos_con_foto[idx]

            parts = []
            parts.append(Paragraph(f"{v.marca} {v.modelo}", estilo_titulo))

            datos = f"<b>{v.dominio}</b> · {v.anio}"
            if v.kilometros:
                datos += f" · {v.kilometros:,.0f} km".replace(",", ".")
            parts.append(Paragraph(datos, estilo_dato))

            # Foto
            if portada:
                try:
                    url = str(portada.imagen.url)
                    if "res.cloudinary.com" in url:
                        url_parts = url.split("/upload/")
                        if len(url_parts) == 2:
                            url = f"{url_parts[0]}/upload/w_350,q_auto,f_jpg/{url_parts[1]}"

                    img_data = BytesIO(urllib.request.urlopen(url).read())
                    img = Image(img_data, width=10 * cm, height=6.5 * cm)
                    img.hAlign = "CENTER"
                    parts.insert(0, img)
                except Exception:
                    parts.insert(0, Paragraph("<i>[Sin foto]</i>", estilo_dato))
            else:
                parts.insert(0, Paragraph("<i>[Sin foto]</i>", estilo_dato))

            parts.append(Spacer(1, 8))
            celdas.append(parts)

        fila = Table([celdas], colWidths=[doc.width / 2, doc.width / 2])
        fila.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        elementos.append(fila)

    # Pie
    elementos.append(Spacer(1, 16))
    elementos.append(Paragraph(
        f"Total: {len(vehiculos_con_foto)} vehículos · Amichetti Automotores · Rojas, Buenos Aires",
        ParagraphStyle("f", fontSize=8, textColor=colors.grey, alignment=1),
    ))

    doc.build(elementos)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="catalogo_amichetti.pdf"'
    return response


# ==========================================================
# PDF RESUMEN DE PUBLICACIONES (USO INTERNO)
# ==========================================================
@login_required
def resumen_publicaciones_pdf(request):
    vehiculos = Vehiculo.objects.filter(estado="stock").order_by("marca", "modelo")

    PLATAFORMAS = [
        ("mercadolibre", "ML"),
        ("facebook", "FB"),
        ("instagram", "IG"),
        ("web", "Web"),
    ]

    hoy = date.today()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20,
    )

    AZUL = colors.HexColor("#002855")
    NARANJA = colors.HexColor("#ff6c1a")
    VERDE = colors.HexColor("#10b981")
    ROJO = colors.HexColor("#ef4444")
    GRIS = colors.HexColor("#f4f6f8")

    elementos = []

    # Header
    header = Table([[
        Paragraph(
            "<b>AMICHETTI AUTOMOTORES</b><br/>Resumen de publicaciones",
            ParagraphStyle("h1", fontSize=14, textColor=colors.white)
        ),
        Paragraph(
            f"Fecha: {hoy.strftime('%d/%m/%Y')}",
            ParagraphStyle("h2", fontSize=10, textColor=colors.white, alignment=2)
        ),
    ]], colWidths=[380, 140])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("LINEBELOW", (0, 0), (-1, -1), 3, NARANJA),
        ("PADDING", (0, 0), (-1, -1), 12),
    ]))
    elementos.append(header)
    elementos.append(Spacer(1, 14))

    # Procesar datos
    rows_completos = []
    rows_faltantes = []
    total_fotos_ok = 0
    total_sin_fotos = 0
    conteo_faltantes = {k: 0 for k, _ in PLATAFORMAS}

    for v in vehiculos:
        fotos_count = v.fotos.count()
        pubs = {p.plataforma: p.publicado for p in v.publicaciones.all()}

        if fotos_count == 0:
            total_sin_fotos += 1
        else:
            total_fotos_ok += 1

        vehiculo_txt = f"{v.marca.upper()} {v.modelo.upper()} {v.anio} ({v.dominio.upper()})"

        faltan = []
        marcas_plat = []
        for key, label in PLATAFORMAS:
            if pubs.get(key, False):
                marcas_plat.append(f"<font color='#10b981'>{label}</font>")
            else:
                marcas_plat.append(f"<font color='#ef4444'>{label}</font>")
                faltan.append(label)
                conteo_faltantes[key] += 1

        plat_str = " · ".join(marcas_plat)
        fotos_str = f"<b>{fotos_count}</b> fotos" if fotos_count > 0 else "<font color='#ef4444'>SIN FOTOS</font>"

        row = [
            Paragraph(vehiculo_txt, ParagraphStyle("v", fontSize=9, fontName="Helvetica-Bold")),
            Paragraph(fotos_str, ParagraphStyle("f", fontSize=9)),
            Paragraph(plat_str, ParagraphStyle("p", fontSize=9)),
            Paragraph(
                ", ".join(faltan) if faltan else "-",
                ParagraphStyle("x", fontSize=9, textColor=ROJO if faltan else colors.grey)
            ),
        ]

        if faltan or fotos_count == 0:
            rows_faltantes.append(row)
        else:
            rows_completos.append(row)

    # Resumen de estadísticas
    total = vehiculos.count()
    total_completos = len(rows_completos)
    total_incompletos = len(rows_faltantes)

    stats_data = [[
        Paragraph(f"<b>{total}</b><br/><font size=8>Total stock</font>",
                  ParagraphStyle("s", fontSize=16, alignment=1)),
        Paragraph(f"<font color='#10b981'><b>{total_completos}</b></font><br/><font size=8>Publicados completos</font>",
                  ParagraphStyle("s", fontSize=16, alignment=1)),
        Paragraph(f"<font color='#ef4444'><b>{total_incompletos}</b></font><br/><font size=8>Falta publicar</font>",
                  ParagraphStyle("s", fontSize=16, alignment=1)),
        Paragraph(f"<font color='#ef4444'><b>{total_sin_fotos}</b></font><br/><font size=8>Sin fotos</font>",
                  ParagraphStyle("s", fontSize=16, alignment=1)),
    ]]
    stats_table = Table(stats_data, colWidths=[130, 130, 130, 130])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
    ]))
    elementos.append(stats_table)
    elementos.append(Spacer(1, 8))

    # Desglose por plataforma
    plat_names = {"mercadolibre": "MercadoLibre", "facebook": "Facebook", "instagram": "Instagram", "web": "Web"}
    plat_data = [["Plataforma", "Faltan publicar"]]
    for key, label in PLATAFORMAS:
        plat_data.append([plat_names[key], str(conteo_faltantes[key])])

    plat_table = Table(plat_data, colWidths=[260, 260])
    plat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    elementos.append(plat_table)
    elementos.append(Spacer(1, 14))

    # SECCIÓN: VEHÍCULOS CON PUBLICACIONES PENDIENTES
    if rows_faltantes:
        elementos.append(Paragraph(
            "<b>PENDIENTES DE PUBLICAR</b>",
            ParagraphStyle("t", fontSize=11, textColor=ROJO, fontName="Helvetica-Bold", spaceAfter=6)
        ))

        header_row = [
            Paragraph("<b>Vehículo</b>", ParagraphStyle("h", fontSize=9, textColor=colors.white)),
            Paragraph("<b>Fotos</b>", ParagraphStyle("h", fontSize=9, textColor=colors.white)),
            Paragraph("<b>Plataformas</b>", ParagraphStyle("h", fontSize=9, textColor=colors.white)),
            Paragraph("<b>Faltan en</b>", ParagraphStyle("h", fontSize=9, textColor=colors.white)),
        ]
        tabla_faltantes = Table(
            [header_row] + rows_faltantes,
            colWidths=[200, 60, 140, 120]
        )
        tabla_faltantes.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
        ]))
        elementos.append(tabla_faltantes)
        elementos.append(Spacer(1, 14))

    # SECCIÓN: VEHÍCULOS PUBLICADOS COMPLETOS
    if rows_completos:
        elementos.append(Paragraph(
            "<b>PUBLICADOS EN TODAS LAS PLATAFORMAS</b>",
            ParagraphStyle("t", fontSize=11, textColor=VERDE, fontName="Helvetica-Bold", spaceAfter=6)
        ))

        header_row = [
            Paragraph("<b>Vehículo</b>", ParagraphStyle("h", fontSize=9, textColor=colors.white)),
            Paragraph("<b>Fotos</b>", ParagraphStyle("h", fontSize=9, textColor=colors.white)),
            Paragraph("<b>Plataformas</b>", ParagraphStyle("h", fontSize=9, textColor=colors.white)),
            Paragraph("", ParagraphStyle("h", fontSize=9)),
        ]
        tabla_completos = Table(
            [header_row] + rows_completos,
            colWidths=[200, 60, 140, 120]
        )
        tabla_completos.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
        ]))
        elementos.append(tabla_completos)

    # Pie
    elementos.append(Spacer(1, 16))
    elementos.append(Paragraph(
        f"Amichetti Automotores · Rojas, Buenos Aires · Generado {hoy.strftime('%d/%m/%Y')}",
        ParagraphStyle("f", fontSize=8, textColor=colors.grey, alignment=1),
    ))

    doc.build(elementos)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="resumen_publicaciones.pdf"'
    return response
