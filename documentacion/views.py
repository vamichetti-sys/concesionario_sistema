from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from vehiculos.models import Vehiculo
from django.db import models
from datetime import date


@login_required
def documentacion_home(request):
    """
    Muestra vehículos con documentación pendiente según el filtro seleccionado
    """
    tipo = request.GET.get('tipo', 'vtv')
    
    # Obtener solo vehículos en stock
    vehiculos = Vehiculo.objects.filter(estado='stock').select_related('ficha')
    
    if tipo == 'vtv':
        # Vehículos SIN VTV o que no tienen el campo informado
        vehiculos = vehiculos.filter(
            models.Q(ficha__vtv_estado='no_tiene') | 
            models.Q(ficha__vtv_estado__isnull=True) |
            models.Q(ficha__vtv_estado='')
        )
        titulo = "VTV Pendiente"
        
    elif tipo == 'autopartes':
        # Vehículos SIN grabado de autopartes
        vehiculos = vehiculos.filter(
            models.Q(ficha__autopartes_estado='no_tiene') | 
            models.Q(ficha__autopartes_estado__isnull=True) |
            models.Q(ficha__autopartes_estado='')
        )
        titulo = "Grabado de Autopartes Pendiente"
        
    elif tipo == 'verificacion':
        # Vehículos SIN verificación policial
        vehiculos = vehiculos.filter(
            models.Q(ficha__verificacion_estado='no_tiene') |
            models.Q(ficha__verificacion_estado__isnull=True) |
            models.Q(ficha__verificacion_estado='')
        )
        titulo = "Verificación Policial Pendiente"

    elif tipo == 'f08':
        # Vehículos SIN Formulario 08
        vehiculos = vehiculos.filter(
            models.Q(ficha__f08_estado='no_tiene') |
            models.Q(ficha__f08_estado__isnull=True) |
            models.Q(ficha__f08_estado='')
        )
        titulo = "Formulario 08 Pendiente"
    
    # ======================================================
    # 🆕 DOCUMENTACIÓN VENCIDA
    # ======================================================
    hoy = date.today()
    vehiculos_vencidos = []
    
    # Obtener todos los vehículos en stock
    todos_vehiculos = Vehiculo.objects.filter(estado='stock').select_related('ficha')
    
    for vehiculo in todos_vehiculos:
        if not vehiculo.ficha:
            continue
            
        ficha = vehiculo.ficha
        vencimientos = []
        
        # Verificar VTV vencida
        if ficha.vtv_vencimiento and ficha.vtv_vencimiento < hoy:
            vencimientos.append({
                'tipo': 'VTV',
                'fecha': ficha.vtv_vencimiento
            })
        
        # Verificar Verificación Policial vencida
        if ficha.verificacion_vencimiento and ficha.verificacion_vencimiento < hoy:
            vencimientos.append({
                'tipo': 'Verificación Policial',
                'fecha': ficha.verificacion_vencimiento
            })
        
        # Verificar Patentes vencidas (todos los vencimientos)
        patentes_vencidas = []
        if ficha.patentes_vto1 and ficha.patentes_vto1 < hoy:
            patentes_vencidas.append(ficha.patentes_vto1)
        if ficha.patentes_vto2 and ficha.patentes_vto2 < hoy:
            patentes_vencidas.append(ficha.patentes_vto2)
        if ficha.patentes_vto3 and ficha.patentes_vto3 < hoy:
            patentes_vencidas.append(ficha.patentes_vto3)
        if ficha.patentes_vto4 and ficha.patentes_vto4 < hoy:
            patentes_vencidas.append(ficha.patentes_vto4)
        if ficha.patentes_vto5 and ficha.patentes_vto5 < hoy:
            patentes_vencidas.append(ficha.patentes_vto5)
        
        if patentes_vencidas:
            # Tomar la fecha más antigua vencida
            fecha_mas_antigua = min(patentes_vencidas)
            vencimientos.append({
                'tipo': 'Patentes',
                'fecha': fecha_mas_antigua
            })
        
        # Si tiene algún vencimiento, agregarlo a la lista
        if vencimientos:
            vehiculos_vencidos.append({
                'vehiculo': vehiculo,
                'vencimientos': vencimientos
            })
    
    return render(
        request,
        'documentacion/home.html',
        {
            'vehiculos': vehiculos,
            'tipo_actual': tipo,
            'titulo': titulo,
            'vehiculos_vencidos': vehiculos_vencidos,
        }
    )


@login_required
def documentacion_pdf(request):
    """
    PDF del listado de vehículos con documentación pendiente
    según el filtro seleccionado (vtv, autopartes, verificacion, f08).
    """
    from reportes.pdf_utils import render_pdf_listado

    tipo = request.GET.get('tipo', 'vtv')

    vehiculos = Vehiculo.objects.filter(estado='stock').select_related('ficha')

    if tipo == 'autopartes':
        vehiculos = vehiculos.filter(
            models.Q(ficha__autopartes_estado='no_tiene') |
            models.Q(ficha__autopartes_estado__isnull=True) |
            models.Q(ficha__autopartes_estado='')
        )
        titulo = "Grabado de Autopartes Pendiente"
    elif tipo == 'verificacion':
        vehiculos = vehiculos.filter(
            models.Q(ficha__verificacion_estado='no_tiene') |
            models.Q(ficha__verificacion_estado__isnull=True) |
            models.Q(ficha__verificacion_estado='')
        )
        titulo = "Verificación Policial Pendiente"
    elif tipo == 'f08':
        vehiculos = vehiculos.filter(
            models.Q(ficha__f08_estado='no_tiene') |
            models.Q(ficha__f08_estado__isnull=True) |
            models.Q(ficha__f08_estado='')
        )
        titulo = "Formulario 08 Pendiente"
    else:
        tipo = 'vtv'
        vehiculos = vehiculos.filter(
            models.Q(ficha__vtv_estado='no_tiene') |
            models.Q(ficha__vtv_estado__isnull=True) |
            models.Q(ficha__vtv_estado='')
        )
        titulo = "VTV Pendiente"

    vehiculos = vehiculos.order_by('marca', 'modelo')

    filas = []
    for v in vehiculos:
        filas.append([
            f"{v.marca} {v.modelo}".strip(),
            v.dominio or "Sin dominio",
            str(v.anio or "—"),
        ])

    return render_pdf_listado(
        filename=f"documentacion_{tipo}.pdf",
        titulo=titulo,
        subtitulo=f"Vehículos en stock pendientes — {date.today().strftime('%d/%m/%Y')}",
        columnas=["Vehículo", "Dominio", "Año"],
        filas=filas,
        totales=["TOTAL", f"{len(filas)} vehículo(s)", ""],
    )