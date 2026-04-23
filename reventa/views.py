from io import BytesIO
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.db import transaction
from django.http import HttpResponse

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

from .models import Reventa
from vehiculos.models import Vehiculo


# ==========================================================
# LISTA DE REVENTAS
# ==========================================================
@login_required
def lista_reventas(request):
    q = request.GET.get("q", "")

    reventas = Reventa.objects.filter(
        estado__in=["pendiente", "confirmada"],
    ).select_related("vehiculo", "cuenta")

    if q:
        reventas = reventas.filter(
            Q(vehiculo__marca__icontains=q)
            | Q(vehiculo__modelo__icontains=q)
            | Q(vehiculo__dominio__icontains=q)
            | Q(agencia__icontains=q)
        )

    pendientes = reventas.filter(estado="pendiente")
    confirmadas = reventas.filter(estado="confirmada")

    return render(request, "reventa/lista.html", {
        "pendientes": pendientes,
        "confirmadas": confirmadas,
        "query": q,
    })


# ==========================================================
# ASIGNAR AGENCIA / COMPRADOR
# ==========================================================
@login_required
def asignar_reventa(request, vehiculo_id):
    from .models import CuentaRevendedor

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    reventa = get_object_or_404(Reventa, vehiculo=vehiculo)

    if reventa.agencia and reventa.estado == "confirmada":
        messages.info(request, "Esta reventa ya tiene agencia asignada y esta confirmada.")
        return redirect("reventa:lista")

    cuentas = CuentaRevendedor.objects.filter(activa=True).order_by("nombre")

    if request.method == "POST":
        cuenta_id = request.POST.get("cuenta_id", "")
        nueva_cuenta = request.POST.get("nueva_cuenta", "").strip()
        precio = request.POST.get("precio_reventa", "").replace(",", ".")
        comision = request.POST.get("comision", "0").replace(",", ".")
        observaciones = request.POST.get("observaciones", "").strip()

        # Seleccionar o crear cuenta
        cuenta = None
        if cuenta_id:
            cuenta = CuentaRevendedor.objects.filter(pk=cuenta_id).first()
        elif nueva_cuenta:
            cuenta = CuentaRevendedor.objects.create(
                nombre=nueva_cuenta,
                contacto=request.POST.get("contacto", "").strip(),
                telefono=request.POST.get("telefono", "").strip(),
            )

        if not cuenta:
            messages.error(request, "Selecciona un revendedor o crea uno nuevo.")
            return redirect("reventa:asignar", vehiculo_id=vehiculo.id)

        reventa.cuenta = cuenta
        reventa.agencia = cuenta.nombre
        reventa.contacto = cuenta.contacto
        reventa.telefono = cuenta.telefono
        reventa.observaciones = observaciones
        reventa.documentacion_entregada = request.POST.get("documentacion_entregada", "").strip()

        try:
            from decimal import Decimal
            if precio:
                reventa.precio_reventa = Decimal(precio)
            if comision:
                reventa.comision = Decimal(comision)
        except Exception:
            pass

        reventa.confirmar()

        messages.success(
            request,
            f"Reventa asignada a \"{cuenta.nombre}\".",
        )
        return redirect("reventa:lista")

    return render(request, "reventa/asignar.html", {
        "vehiculo": vehiculo,
        "reventa": reventa,
        "cuentas": cuentas,
    })


# ==========================================================
# REVERTIR REVENTA (VOLVER A STOCK)
# ==========================================================
# ==========================================================
# EDITAR REVENTA
# ==========================================================
@login_required
def editar_reventa(request, reventa_id):
    reventa = get_object_or_404(Reventa, id=reventa_id)

    if request.method == "POST":
        reventa.agencia = request.POST.get("agencia", "").strip()
        reventa.contacto = request.POST.get("contacto", "").strip()
        reventa.telefono = request.POST.get("telefono", "").strip()
        reventa.observaciones = request.POST.get("observaciones", "").strip()
        reventa.documentacion_entregada = request.POST.get("documentacion_entregada", "").strip()

        precio = request.POST.get("precio_reventa", "").replace(",", ".")
        comision = request.POST.get("comision", "0").replace(",", ".")

        try:
            from decimal import Decimal
            if precio:
                reventa.precio_reventa = Decimal(precio)
            if comision:
                reventa.comision = Decimal(comision)
        except Exception:
            pass

        reventa.save()
        messages.success(request, "Reventa actualizada.")
        return redirect("reventa:lista")

    return render(request, "reventa/editar.html", {
        "reventa": reventa,
        "vehiculo": reventa.vehiculo,
    })


@login_required
@transaction.atomic
def revertir_reventa(request, reventa_id):
    reventa = get_object_or_404(Reventa, id=reventa_id)

    if request.method == "POST":
        vehiculo = reventa.vehiculo
        reventa.revertir()

        messages.success(
            request,
            f"Reventa revertida. {vehiculo} volvio a stock.",
        )

    return redirect("reventa:lista")


# ==========================================================
# ELIMINAR REVENTA
# ==========================================================
@login_required
def eliminar_reventa(request, reventa_id):
    reventa = get_object_or_404(Reventa, id=reventa_id)

    if request.method == "POST":
        vehiculo = reventa.vehiculo
        if vehiculo and vehiculo.estado == "reventa":
            vehiculo.estado = "stock"
            vehiculo.save(update_fields=["estado"])
        reventa.delete()
        messages.success(request, "Reventa eliminada.")

    return redirect("reventa:lista")


# ==========================================================
# CUENTAS DE REVENDEDORES
# ==========================================================
@login_required
def lista_cuentas_revendedores(request):
    q = request.GET.get("q", "")
    from .models import CuentaRevendedor
    cuentas = CuentaRevendedor.objects.filter(activa=True)
    if q:
        cuentas = cuentas.filter(Q(nombre__icontains=q))

    from django.db.models import Sum
    total_deuda = cuentas.filter(saldo__gt=0).aggregate(t=Sum("saldo"))["t"] or 0

    return render(request, "reventa/cuentas_lista.html", {
        "cuentas": cuentas,
        "query": q,
        "total_deuda": total_deuda,
    })


@login_required
def crear_cuenta_revendedor(request):
    from .models import CuentaRevendedor
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        contacto = request.POST.get("contacto", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        direccion = request.POST.get("direccion", "").strip()

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return redirect("reventa:crear_cuenta")

        CuentaRevendedor.objects.create(
            nombre=nombre,
            contacto=contacto,
            telefono=telefono,
            direccion=direccion,
        )
        messages.success(request, f"Cuenta \"{nombre}\" creada.")
        return redirect("reventa:cuentas")

    return render(request, "reventa/cuenta_form.html", {
        "titulo": "Nueva Cuenta de Revendedor",
    })


@login_required
def detalle_cuenta_revendedor(request, pk):
    from .models import CuentaRevendedor
    cuenta = get_object_or_404(CuentaRevendedor, pk=pk)
    movimientos = cuenta.movimientos.all()

    return render(request, "reventa/cuenta_detalle.html", {
        "cuenta": cuenta,
        "movimientos": movimientos,
    })


@login_required
def agregar_movimiento_revendedor(request, pk):
    from .models import CuentaRevendedor, MovimientoRevendedor
    cuenta = get_object_or_404(CuentaRevendedor, pk=pk)

    if request.method == "POST":
        tipo = request.POST.get("tipo", "debe")
        monto_raw = request.POST.get("monto", "0").replace(",", ".")
        descripcion = request.POST.get("descripcion", "").strip()

        if not descripcion:
            messages.error(request, "La descripcion es obligatoria.")
            return redirect("reventa:detalle_cuenta", pk=cuenta.pk)

        try:
            from decimal import Decimal
            monto = Decimal(monto_raw)
        except Exception:
            messages.error(request, "Monto invalido.")
            return redirect("reventa:detalle_cuenta", pk=cuenta.pk)

        MovimientoRevendedor.objects.create(
            cuenta=cuenta,
            tipo=tipo,
            monto=monto,
            descripcion=descripcion,
        )
        messages.success(request, "Movimiento registrado.")

    return redirect("reventa:detalle_cuenta", pk=cuenta.pk)


@login_required
def eliminar_movimiento_revendedor(request, pk):
    from .models import MovimientoRevendedor
    movimiento = get_object_or_404(MovimientoRevendedor, pk=pk)
    cuenta_pk = movimiento.cuenta.pk

    if request.method == "POST":
        movimiento.delete()
        messages.success(request, "Movimiento eliminado.")

    return redirect("reventa:detalle_cuenta", pk=cuenta_pk)


# ==========================================================
# ACTA DE ENTREGA EN CONSIGNACIÓN - PDF
# ==========================================================
TITULARES = {
    "valentina": {
        "nombre": "AMICHETTI, VALENTINA",
        "dni": "40.883.059",
        "genero": "F",
        "tratamiento": "Sra.",
        "nombre_firma": "Valentina Amichetti",
        "dni_firma": "40.883.059",
        "rol_firma": "LA PROPIETARIA",
    },
    "hugo": {
        "nombre": "AMICHETTI, HUGO ALBERTO",
        "dni": "13.814.200",
        "genero": "M",
        "tratamiento": "Sr.",
        "nombre_firma": "Hugo Alberto Amichetti",
        "dni_firma": "13.814.200",
        "rol_firma": "EL PROPIETARIO",
    },
}


@login_required
def acta_entrega_pdf(request, reventa_id):
    reventa = get_object_or_404(Reventa, id=reventa_id)
    vehiculo = reventa.vehiculo
    cuenta = reventa.cuenta
    ficha = getattr(vehiculo, "ficha", None) if vehiculo else None

    titular_key = request.GET.get("titular", "valentina").lower()
    titular = TITULARES.get(titular_key, TITULARES["valentina"])

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    ML = 2 * cm
    MR = 2 * cm
    CW = page_w - ML - MR
    GRIS = colors.HexColor("#999999")
    NEGRO = colors.black

    def linea_punt(x1, x2, yy):
        c.setStrokeColor(GRIS); c.setLineWidth(0.4)
        c.line(x1, yy - 0.05 * cm, x2, yy - 0.05 * cm)
        c.setStrokeColor(NEGRO)

    def campo(label, valor, x, y, ancho_label, ancho_total):
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, y, label)
        lx = x + ancho_label
        linea_punt(lx, x + ancho_total, y)
        if valor:
            c.setFont("Helvetica", 8)
            c.drawString(lx + 0.1 * cm, y, str(valor))

    def sec_header(titulo, y):
        c.setFillColor(NEGRO)
        c.rect(ML, y - 0.08 * cm, CW, 0.5 * cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(ML + 0.2 * cm, y + 0.05 * cm, titulo)
        c.setFillColor(NEGRO)
        return y - 0.7 * cm

    def wrap_text(texto, font, size, max_width):
        palabras = texto.split()
        lineas = []
        actual = ""
        for p in palabras:
            prueba = (actual + " " + p).strip()
            if c.stringWidth(prueba, font, size) < max_width:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = p
        if actual:
            lineas.append(actual)
        return lineas

    def draw_wrapped(texto, x, y, font, size, max_width, line_h=0.36 * cm):
        for linea in wrap_text(texto, font, size, max_width):
            c.setFont(font, size)
            c.drawString(x, y, linea)
            y -= line_h
        return y

    def nueva_pagina(y_min):
        nonlocal y
        if y < y_min:
            c.showPage()
            y = page_h - 1.5 * cm

    # ========== HEADER ==========
    y = page_h - 1.5 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(ML, y, "AMICHETTI AUTOMOTORES")
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(page_w - MR, y, f"ACTA N°: {reventa.id:04d}")
    y -= 0.42 * cm
    c.setFont("Helvetica", 8)
    c.drawString(ML, y, "Rojas, Provincia de Buenos Aires")
    hoy = date.today()
    c.drawRightString(
        page_w - MR, y,
        f"FECHA: {hoy.strftime('%d')} / {hoy.strftime('%m')} / {hoy.strftime('%Y')}"
    )
    y -= 0.3 * cm
    c.setStrokeColor(NEGRO); c.setLineWidth(1)
    c.line(ML, y, page_w - MR, y)
    y -= 0.7 * cm

    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(page_w / 2, y, "ACTA DE ENTREGA DE VEHÍCULO EN CONSIGNACIÓN")
    y -= 0.5 * cm
    c.setFont("Helvetica", 8)
    c.drawCentredString(page_w / 2, y, "Para Comercialización por Agencia Revendedora")
    y -= 0.8 * cm

    # ========== 1. PARTES ==========
    y = sec_header("1. PARTES INTERVINIENTES", y)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(ML, y, "EL PROPIETARIO / ENTREGANTE:")
    y -= 0.5 * cm

    label_titular = "Titular / Propietaria:" if titular["genero"] == "F" else "Titular / Propietario:"
    campo(label_titular, titular["nombre"], ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("DNI:", titular["dni"], ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Actividad comercial:", "AMICHETTI AUTOMOTORES", ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Domicilio Comercial:", "", ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Localidad:", "Rojas, Provincia de Buenos Aires", ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Teléfono de contacto:", "", ML, y, 3.5 * cm, CW); y -= 0.7 * cm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(ML, y, "EL REVENDEDOR / RECEPTOR:")
    y -= 0.5 * cm

    revendedor_nombre = cuenta.nombre if cuenta else (reventa.agencia or "")
    revendedor_dir = cuenta.direccion if cuenta else ""
    revendedor_contacto = cuenta.contacto if cuenta else (reventa.contacto or "")
    revendedor_tel = cuenta.telefono if cuenta else (reventa.telefono or "")

    campo("Razón Social / Nombre:", revendedor_nombre, ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("CUIT / CUIL:", "", ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Domicilio Comercial:", revendedor_dir, ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Localidad:", "", ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Representado por:", revendedor_contacto, ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("DNI:", "", ML, y, 3.5 * cm, CW); y -= 0.5 * cm
    campo("Teléfono de contacto:", revendedor_tel, ML, y, 3.5 * cm, CW); y -= 0.8 * cm

    # ========== 2. VEHICULO ==========
    y = sec_header("2. DATOS DEL VEHÍCULO ENTREGADO", y)

    marca = vehiculo.marca if vehiculo else ""
    modelo = vehiculo.modelo if vehiculo else ""
    anio = vehiculo.anio if vehiculo else ""
    dominio = vehiculo.dominio if vehiculo else ""
    motor = ficha.numero_motor if ficha and ficha.numero_motor else ""
    chasis = ficha.numero_chasis if ficha and ficha.numero_chasis else ""

    mitad = ML + CW / 2 + 0.3 * cm
    ancho_col = CW / 2 - 0.3 * cm
    campo("Marca:", marca, ML, y, 1.8 * cm, ancho_col)
    campo("Modelo:", modelo, mitad, y, 1.8 * cm, ancho_col); y -= 0.5 * cm
    campo("Año:", str(anio) if anio else "", ML, y, 1.8 * cm, ancho_col)
    campo("Color:", "", mitad, y, 1.8 * cm, ancho_col); y -= 0.5 * cm
    campo("Dominio / Patente:", dominio, ML, y, 2.7 * cm, ancho_col)
    campo("Tipo:", "", mitad, y, 1.8 * cm, ancho_col); y -= 0.5 * cm
    campo("N° de Motor:", motor, ML, y, 2.2 * cm, ancho_col)
    campo("N° de Chasis:", chasis, mitad, y, 2.2 * cm, ancho_col); y -= 0.5 * cm
    campo("Kilometraje:", "", ML, y, 2.2 * cm, ancho_col)
    campo("Combustible:", "", mitad, y, 2.2 * cm, ancho_col); y -= 0.7 * cm

    c.setFont("Helvetica", 8)
    c.drawString(ML, y, "Documentación entregada (marcar con cruz lo que corresponda):")
    y -= 0.5 * cm

    items = [
        "Título del Automotor", "Cédula Verde (Titular)", "Cédula Azul",
        "Verificación Policial", "Formulario 08 firmado", "Libre de deuda",
        "VTV vigente", "Manual del usuario", "Service oficial",
        "Juego de llaves (cant: ____)", "Rueda de auxilio", "Otros: ____________",
    ]
    col_w = CW / 3
    for i, item in enumerate(items):
        col = i % 3
        if col == 0 and i > 0:
            y -= 0.45 * cm
        x_item = ML + col * col_w
        c.rect(x_item, y - 0.05 * cm, 0.25 * cm, 0.25 * cm, stroke=1, fill=0)
        c.setFont("Helvetica", 8)
        c.drawString(x_item + 0.4 * cm, y, item)
    y -= 0.7 * cm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(ML, y, "Estado general del vehículo al momento de la entrega:")
    y -= 0.4 * cm
    for _ in range(3):
        linea_punt(ML, page_w - MR, y)
        y -= 0.5 * cm
    y -= 0.2 * cm

    # Nueva pagina si queda poco
    if y < 6 * cm:
        c.showPage()
        y = page_h - 1.5 * cm

    # ========== 3. CONDICIONES ==========
    y = sec_header("3. CONDICIONES Y DECLARACIONES DE LAS PARTES", y)

    clausulas = [
        ("PRIMERA — TITULARIDAD DEL VEHÍCULO.",
         f"El vehículo descripto en la cláusula 2 es de exclusiva propiedad del/la {titular['tratamiento']} {titular['nombre']}, DNI N° {titular['dni']}, quien lo comercializa bajo el nombre de fantasía AMICHETTI AUTOMOTORES, conservando la titularidad registral, dominial y el pleno dominio del mismo hasta tanto se perfeccione una operación de compraventa formal y se abone íntegramente el precio acordado. La presente entrega no implica, bajo ningún concepto, transferencia de propiedad al Revendedor."),
        ("SEGUNDA — FINALIDAD DE LA ENTREGA.",
         "El vehículo se entrega al Revendedor con el único y exclusivo fin de ser exhibido y ofrecido a potenciales compradores, no autorizándose ningún otro uso, afectación, cesión, gravamen ni disposición sobre el mismo."),
        ("TERCERA — RESPONSABILIDAD INTEGRAL DEL REVENDEDOR.",
         "A partir de la firma de la presente, el Revendedor asume total y exclusiva responsabilidad sobre el vehículo, incluyendo —sin que la enumeración sea taxativa— los siguientes conceptos: daños materiales (parciales o totales), siniestros, robo, hurto, incendio, desperfectos mecánicos, multas, infracciones de tránsito, peajes, consumos de combustible, traslados, estadía y cualquier otro gasto, riesgo o contingencia que se produzca sobre o con motivo del vehículo mientras se encuentre bajo su guarda."),
        ("CUARTA — DAÑOS Y SINIESTROS.",
         "En caso de producirse cualquier daño, siniestro, robo, hurto o pérdida total o parcial del vehículo durante el período de tenencia por parte del Revendedor, éste se obliga a reparar el vehículo a su exclusivo costo, dejándolo en las mismas condiciones en que fue recibido, o bien a abonar en forma íntegra el valor del vehículo a la Propietaria, a simple requerimiento de ésta y sin derecho a reclamo ni compensación alguna."),
        ("QUINTA — MULTAS, INFRACCIONES Y DEUDAS.",
         "Toda multa, infracción de tránsito, peaje, acarreo, estadía o cualquier otra obligación de naturaleza económica que se devengue sobre el vehículo desde la firma de esta Acta y hasta su efectiva devolución o venta, será de exclusiva cuenta y cargo del Revendedor, quien deberá cancelarla en forma previa a la restitución del vehículo o, en su defecto, autorizar expresamente a la Propietaria a descontarla de cualquier suma que tuviera a favor."),
        ("SEXTA — PROHIBICIÓN DE USO PARTICULAR.",
         "El Revendedor declara que el vehículo no será destinado a uso particular, familiar, laboral ni a ninguna actividad distinta a la exhibición para venta. Queda expresamente prohibido circular con el mismo fuera de lo estrictamente necesario para su traslado, exhibición y prueba de manejo supervisada a potenciales compradores."),
        ("SÉPTIMA — VENTA Y RENDICIÓN DE CUENTAS.",
         "En caso de concretarse un interesado en la compra, el Revendedor se obliga a comunicarlo previamente a la Propietaria a fin de acordar condiciones finales, precio y documentación. La operación de compraventa, firma del boleto, emisión del Formulario 08 y cobro del precio se realizarán exclusivamente por la Propietaria, o bajo las instrucciones escritas que ésta imparta. La comisión o diferencia que corresponda al Revendedor será la pactada en forma separada por escrito."),
        ("OCTAVA — PLAZO DE TENENCIA.",
         "El plazo durante el cual el Revendedor podrá conservar el vehículo en su poder será el siguiente: ____________________________. Vencido dicho plazo sin haberse concretado la venta, el Revendedor deberá restituir el vehículo de inmediato, en las mismas condiciones en que fue recibido, junto con la totalidad de la documentación y accesorios detallados en la cláusula 2."),
        ("NOVENA — RESTITUCIÓN.",
         "La Propietaria podrá exigir la devolución del vehículo en cualquier momento, sin necesidad de expresión de causa ni preaviso, debiendo el Revendedor restituirlo dentro de las 24 (veinticuatro) horas de recibida la comunicación fehaciente."),
        ("DÉCIMA — INCUMPLIMIENTO.",
         "La falta de restitución en el plazo convenido, el uso indebido del vehículo, su afectación a terceros o cualquier otro incumplimiento de las obligaciones asumidas en la presente habilitará a la Propietaria a iniciar de inmediato las acciones civiles y penales que correspondan, incluyendo —sin que la enumeración sea taxativa— la denuncia por retención indebida y/o apropiación ilegítima del vehículo."),
        ("DÉCIMO PRIMERA — SEGURO.",
         "El Revendedor declara conocer que la contratación y mantenimiento de un seguro contra todo riesgo sobre el vehículo durante el período de tenencia queda a su exclusivo cargo, sin perjuicio de lo cual su responsabilidad frente a la Propietaria subsiste íntegramente aun cuando no lo hubiera contratado o cuando la compañía aseguradora rechazara el siniestro por cualquier motivo."),
        ("DÉCIMO SEGUNDA — DOMICILIOS Y JURISDICCIÓN.",
         "Las partes constituyen domicilios en los indicados en la cláusula 1, donde se tendrán por válidas todas las notificaciones y comunicaciones que se cursen. Para cualquier cuestión derivada de la presente, las partes se someten a la jurisdicción de los Tribunales Ordinarios de Rojas, Provincia de Buenos Aires, con renuncia expresa a cualquier otro fuero o jurisdicción que pudiera corresponder."),
    ]

    for titulo, cuerpo in clausulas:
        if y < 3.5 * cm:
            c.showPage()
            y = page_h - 1.5 * cm

        c.setFont("Helvetica-Bold", 8)
        ancho_titulo = c.stringWidth(titulo + " ", "Helvetica-Bold", 8)
        c.drawString(ML, y, titulo)

        primera = cuerpo
        primera_lineas = wrap_text(primera, "Helvetica", 8, CW - ancho_titulo)
        if primera_lineas:
            c.setFont("Helvetica", 8)
            c.drawString(ML + ancho_titulo, y, primera_lineas[0])
            y -= 0.36 * cm
            for linea in primera_lineas[1:]:
                if y < 2 * cm:
                    c.showPage()
                    y = page_h - 1.5 * cm
                c.setFont("Helvetica", 8)
                c.drawString(ML, y, linea)
                y -= 0.36 * cm
        else:
            y -= 0.36 * cm
        y -= 0.15 * cm

    # ========== FIRMAS ==========
    if y < 5 * cm:
        c.showPage()
        y = page_h - 1.5 * cm
    else:
        y -= 0.5 * cm

    c.setFont("Helvetica", 8)
    cierre = (
        "En prueba de conformidad, previa lectura y ratificación, las partes firman DOS (2) ejemplares "
        "de un mismo tenor y a un solo efecto, en la ciudad de ____________________, a los _______ "
        "días del mes de ____________________ del año __________."
    )
    y = draw_wrapped(cierre, ML, y, "Helvetica", 8, CW)
    y -= 1.5 * cm

    mitad_x = page_w / 2
    c.setStrokeColor(NEGRO); c.setLineWidth(0.5)
    c.line(ML, y, mitad_x - 1 * cm, y)
    c.line(mitad_x + 1 * cm, y, page_w - MR, y)
    y -= 0.4 * cm
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString((ML + mitad_x - 1 * cm) / 2, y, titular["rol_firma"])
    c.drawCentredString((mitad_x + 1 * cm + page_w - MR) / 2, y, "EL REVENDEDOR")
    y -= 0.35 * cm
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(
        (ML + mitad_x - 1 * cm) / 2, y,
        f"{titular['nombre_firma']} · DNI {titular['dni_firma']}"
    )
    c.drawCentredString((mitad_x + 1 * cm + page_w - MR) / 2, y, "Firma, aclaración y DNI")
    y -= 0.3 * cm
    c.drawCentredString((ML + mitad_x - 1 * cm) / 2, y, "Amichetti Automotores")

    c.setFont("Helvetica", 6.5); c.setFillColor(GRIS)
    c.drawCentredString(
        page_w / 2, 1.2 * cm,
        "Documento emitido por Amichetti Automotores — Rojas, Buenos Aires. "
        "Se firma en dos ejemplares originales, quedando uno en poder de cada parte."
    )
    c.setFillColor(NEGRO)

    c.save()
    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="acta_entrega_{reventa.id:04d}.pdf"'
    )
    return response
