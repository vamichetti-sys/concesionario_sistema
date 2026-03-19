from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Max, Q
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.conf import settings
import re
from decimal import Decimal
from datetime import date
from io import BytesIO

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

from .models import BoletoCompraventa, Pagare, PagareLote
from .forms import CrearBoletoForm, CrearPagareLoteForm
from clientes.models import Cliente
from cuentas.models import CuentaCorriente


# ====================================
# 🟢 PANEL DE BOLETOS
# ====================================
def panel_boletos(request):
    return render(request, "boletos/panel.html")


# ====================================
# LISTA + BUSCADOR DE BOLETOS
# ====================================
def lista_boletos(request):
    q = request.GET.get("q", "")
    boletos = BoletoCompraventa.objects.all()

    if q:
        boletos = boletos.filter(Q(texto_final__icontains=q))

    return render(
        request,
        "boletos/lista.html",
        {"boletos": boletos, "query": q}
    )


# ====================================
# GENERAR PDF BOLETO DESDE HTML
# ====================================
def generar_boleto_pdf_desde_html(request, boleto):
    from weasyprint import HTML

    cliente = boleto.cliente
    nombre_completo = cliente.nombre_completo or ""
    partes = nombre_completo.strip().split(" ", 1)

    apellido_cliente = partes[0] if partes else ""
    nombre_cliente = partes[1] if len(partes) > 1 else ""

    html_string = render_to_string(
        "boletos/ver.html",
        {
            "boleto": boleto,
            "texto_boleto": boleto.texto_final,
            "vendedor": {
                "apellido": "AMICHETTI",
                "nombre": "HUGO ALBERTO",
                "direccion": "LARREA 255, ROJAS",
                "dni": "13814200",
            },
            "comprador": {
                "apellido": apellido_cliente,
                "nombre": nombre_cliente,
                "direccion": cliente.direccion or "",
                "dni": cliente.dni_cuit or "",
            },
        },
        request=request
    )

    buffer = BytesIO()
    HTML(
        string=html_string,
        base_url=request.build_absolute_uri()
    ).write_pdf(buffer)

    buffer.seek(0)
    return ContentFile(buffer.read())


# ====================================
# CREAR BOLETO
# ====================================
def crear_boleto_manual(request):
    ultimo = BoletoCompraventa.objects.aggregate(
        numero_max=Max("numero")
    )["numero_max"] or 0

    numero = ultimo + 1

    if request.method == "POST":
        form = CrearBoletoForm(request.POST)

        if form.is_valid():
            f = form.cleaned_data
            cliente = f["cliente"]
            vehiculo = f.get("vehiculo")

            if not vehiculo:
                messages.error(request, "❌ Debe seleccionar un vehículo.")
                return render(
                    request,
                    "boletos/crear.html",
                    {"form": form, "numero": numero}
                )

            marca = vehiculo.marca
            modelo = vehiculo.modelo
            anio = vehiculo.anio
            dominio = vehiculo.dominio

            ficha = getattr(vehiculo, "ficha", None)
            motor = getattr(ficha, "numero_motor", "") if ficha else ""
            chasis = getattr(ficha, "numero_chasis", "") if ficha else ""

            if not cliente or not cliente.activo:
                messages.error(request, "❌ Cliente inválido.")
                return render(
                    request,
                    "boletos/crear.html",
                    {"form": form, "numero": numero}
                )

            cuenta_activa = (
                CuentaCorriente.objects
                .filter(cliente=cliente)
                .exclude(estado="cerrada")
                .first()
            )

            venta = (
                cuenta_activa.venta
                if cuenta_activa and hasattr(cuenta_activa, "venta")
                else None
            )

            texto_final = f"""
Entre el/los Señor/es {cliente.nombre_completo} por una parte como comprador
y el/los Señor/es AMICHETTI HUGO ALBERTO por la otra parte como vendedor,
convienen celebrar el presente boleto de acuerdo a las cláusulas siguientes:

1° - El vendedor vende a {cliente.nombre_completo} un vehículo Marca {marca}
Modelo {modelo} Año {anio} Motor {motor}
Chasis {chasis} Dominio {dominio} en el estado que se encuentra, y que el comprador 
ha revisado y controlado las numeraciones de motor, chasis y dominio, aceptando el
mismo de conformidad.
2° - El vendedor entrega en este acto toda la documentación referente al vehículo
y el comprador se obliga a realizar la respectiva transferencia dentro de los
treinta (30) días a partir de la fecha.
3° - Los gastos que demande la transferencia del vehículo en el orden nacional, provincial, 
municipal, o de cualquier otro orden serán abonados por el comprador, y lo correspondiente 
a la Ley 21.432/976.-
4° - El comprador deberá asegurar el automotor contra todo riesgo dentro de los dos dias de 
la fecha presente en el boleto, siendo el endoso a favor del vendedor.-
5° - El comprador no podrá vender el vehículo sin autorización expresa del vendedor
hasta no haber abonado la totalidad de la deuda.-
6° - La falta de cumplimiento de cualquiera de las cláusulas del contrato autoriza al 
vendedor a solicitar el inmediato secuestro del vehículo, renunciando el comprador a toda 
defensa en juicio
7° - El vendedor podra optar para el caso en el que el comprador se constituya en mora 
de alguna de las cuotas, por pedir el secuestro judicial de la unidad vendida constituyendo 
el comprador para el caso de promover accion judicial, domicilio legal en {cliente.direccion or "LARREA 255"}
Que asimismo y tambien para el caso de promover acción judicial, queda facultado el vendedor 
a nombrar martillero, comprometiendose el comprador a no poner otra excepcion que la de pago
y renunciando expresamente a la facultad de apelar la resolucion dictada.
8° - Todos los gastos judiciales que se originen serán a cargo del comprador.
9° - El precio total de la unidad es de {f.get("precio_numeros")}({f.get("precio_letras")}),
quedando un saldo conforme la siguiente modalidad de pago: {f.get("saldo_forma_pago")}
10° - La mora en el pago de todas las cuotas convenidas como saldo de precio se producira
por el mero vencimiento de una de ellas, sin necesidad de interpelacion judicial o extra 
judicial de ninguna naturaleza, al producirse dicha mora el deudor perdera automaticamente
a favor del vendedor todo lo abonado hasta esa fecha y la operacion quedara rescindida, 
obligandose al comprador a devolver el vehiculo en ese mismo momento. De no hacerlo asi, 
pagara una multa diaria de acuerdo a los daños y perjuicios ocasionados al vendedor mas toda
otra indemnizacion que por ley correspondiere, pudiendo los vendedores a partir de ese momento
disponer del vehiculo arriba citado. Se deja perfectamente aclarado que este recibo es provisorio, 
debiendo el comprador gestionar directamente ante el titular o ante quien corresponda la transferencia
del vehiculo arriba citado.-
11° - El comprador pagara el 3% para gastos de prenda y el 1% para sellado. El comprador se hace 
responsable civil y criminalmente ante quien corresponda de los daños que ocasionara con este 
vehiculo a partir de la fecha. En fe de cual se firman dos ejemplares de un mismo tenor y a un solo efecto 
En la ciudad de ROJAS, a los {date.today().strftime("%d/%m/%Y")}.

LA UNIDAD HA SIDO REVISADA Y ACEPTADA EN CONFORMIDAD.
"""

            boleto = BoletoCompraventa.objects.create(
                numero=numero,
                cliente=cliente,
                vehiculo=vehiculo,
                cuenta_corriente=cuenta_activa,
                venta=venta,
                texto_final=texto_final
            )

            try:
                pdf_file = generar_boleto_pdf_desde_html(request, boleto)
                boleto.pdf.save(
                    f"boleto_{boleto.numero}.pdf",
                    pdf_file,
                    save=True
                )
            except Exception as e:
                print("❌ ERROR PDF BOLETO:", e)
                messages.warning(
                    request,
                    "⚠️ El boleto se creó correctamente, pero el PDF no pudo generarse."
                )

            messages.success(request, "✅ Boleto generado correctamente")
            return redirect("boletos:ver_boleto", boleto.id)

    return render(
        request,
        "boletos/crear.html",
        {"form": CrearBoletoForm(), "numero": numero}
    )


# ====================================
# VER BOLETO
# ====================================
def ver_boleto(request, boleto_id):
    boleto = get_object_or_404(BoletoCompraventa, id=boleto_id)

    texto_boleto = re.sub(
        r"\n\s*\n+", "\n", (boleto.texto_final or "").strip()
    )

    vendedor = {
        "apellido": "AMICHETTI",
        "nombre": "HUGO ALBERTO",
        "direccion": "LARREA 155",
        "dni": "13814200",
    }

    cliente = boleto.cliente
    nombre_completo = (cliente.nombre_completo or "").strip()
    partes = nombre_completo.split(" ", 1)

    comprador = {
        "apellido": partes[0] if partes else "",
        "nombre": partes[1] if len(partes) > 1 else "",
        "direccion": cliente.direccion or "",
        "dni": cliente.dni_cuit or "",
    }

    # Unir líneas de la misma cláusula, separar solo por cláusula numerada
    texto_limpio = re.sub(r'\n(?!\d+[°])', ' ', texto_boleto)
    texto_limpio = re.sub(r' +', ' ', texto_limpio)
    clausulas = [p.strip() for p in texto_limpio.split("\n") if p.strip()]

    return render(
        request,
        "boletos/ver.html",
        {
            "boleto": boleto,
            "texto_boleto": texto_boleto,
            "clausulas": clausulas,
            "vendedor": vendedor,
            "comprador": comprador,
        }
    )


# ====================================
# EDITAR BOLETO
# ====================================
def editar_boleto(request, boleto_id):
    boleto = get_object_or_404(BoletoCompraventa, id=boleto_id)

    from .forms import EditarBoletoForm

    # Pre-poblar precio/forma de pago extrayéndolos del texto_final existente
    precio_numeros_inicial = ""
    precio_letras_inicial = ""
    saldo_forma_pago_inicial = ""

    if boleto.texto_final:
        match_9 = re.search(
            r"9°.*?precio total.*?es de\s*(.*?)\((.*?)\),\s*quedando.*?modalidad de pago:\s*(.*?)(?=10°|\Z)",
            boleto.texto_final,
            re.DOTALL | re.IGNORECASE
        )
        if match_9:
            precio_numeros_inicial   = match_9.group(1).strip()
            precio_letras_inicial    = match_9.group(2).strip()
            saldo_forma_pago_inicial = match_9.group(3).strip()

    if request.method == "POST":
        form = EditarBoletoForm(request.POST, instance=boleto)
        if form.is_valid():
            boleto = form.save(commit=False)

            cliente  = boleto.cliente
            vehiculo = boleto.vehiculo

            marca   = vehiculo.marca   if vehiculo else ""
            modelo  = vehiculo.modelo  if vehiculo else ""
            anio    = vehiculo.anio    if vehiculo else ""
            dominio = vehiculo.dominio if vehiculo else ""

            ficha  = getattr(vehiculo, "ficha", None) if vehiculo else None
            motor  = getattr(ficha, "numero_motor",  "") if ficha else ""
            chasis = getattr(ficha, "numero_chasis", "") if ficha else ""

            precio_numeros   = form.cleaned_data.get("precio_numeros", "")
            precio_letras    = form.cleaned_data.get("precio_letras", "")
            saldo_forma_pago = form.cleaned_data.get("saldo_forma_pago", "")

            boleto.texto_final = f"""
Entre el/los Señor/es {cliente.nombre_completo} por una parte como comprador
y el/los Señor/es AMICHETTI HUGO ALBERTO por la otra parte como vendedor,
convienen celebrar el presente boleto de acuerdo a las cláusulas siguientes:

1° - El vendedor vende a {cliente.nombre_completo} un vehículo Marca {marca}
Modelo {modelo} Año {anio} Motor {motor}
Chasis {chasis} Dominio {dominio} en el estado que se encuentra, y que el comprador 
ha revisado y controlado las numeraciones de motor, chasis y dominio, aceptando el
mismo de conformidad.
2° - El vendedor entrega en este acto toda la documentación referente al vehículo
y el comprador se obliga a realizar la respectiva transferencia dentro de los
treinta (30) días a partir de la fecha.
3° - Los gastos que demande la transferencia del vehículo en el orden nacional, provincial, 
municipal, o de cualquier otro orden serán abonados por el comprador, y lo correspondiente 
a la Ley 21.432/976.-
4° - El comprador deberá asegurar el automotor contra todo riesgo dentro de los dos dias de 
la fecha presente en el boleto, siendo el endoso a favor del vendedor.-
5° - El comprador no podrá vender el vehículo sin autorización expresa del vendedor
hasta no haber abonado la totalidad de la deuda.-
6° - La falta de cumplimiento de cualquiera de las cláusulas del contrato autoriza al 
vendedor a solicitar el inmediato secuestro del vehículo, renunciando el comprador a toda 
defensa en juicio
7° - El vendedor podra optar para el caso en el que el comprador se constituya en mora 
de alguna de las cuotas, por pedir el secuestro judicial de la unidad vendida constituyendo 
el comprador para el caso de promover accion judicial, domicilio legal en {cliente.direccion or "LARREA 255"}
Que asimismo y tambien para el caso de promover acción judicial, queda facultado el vendedor 
a nombrar martillero, comprometiendose el comprador a no poner otra excepcion que la de pago
y renunciando expresamente a la facultad de apelar la resolucion dictada.
8° - Todos los gastos judiciales que se originen serán a cargo del comprador.
9° - El precio total de la unidad es de {precio_numeros}({precio_letras}),
quedando un saldo conforme la siguiente modalidad de pago: {saldo_forma_pago}
10° - La mora en el pago de todas las cuotas convenidas como saldo de precio se producira
por el mero vencimiento de una de ellas, sin necesidad de interpelacion judicial o extra 
judicial de ninguna naturaleza, al producirse dicha mora el deudor perdera automaticamente
a favor del vendedor todo lo abonado hasta esa fecha y la operacion quedara rescindida, 
obligandose al comprador a devolver el vehiculo en ese mismo momento. De no hacerlo asi, 
pagara una multa diaria de acuerdo a los daños y perjuicios ocasionados al vendedor mas toda
otra indemnizacion que por ley correspondiere, pudiendo los vendedores a partir de ese momento
disponer del vehiculo arriba citado. Se deja perfectamente aclarado que este recibo es provisorio, 
debiendo el comprador gestionar directamente ante el titular o ante quien corresponda la transferencia
del vehiculo arriba citado.-
11° - El comprador pagara el 3% para gastos de prenda y el 1% para sellado. El comprador se hace 
responsable civil y criminalmente ante quien corresponda de los daños que ocasionara con este 
vehiculo a partir de la fecha. En fe de cual se firman dos ejemplares de un mismo tenor y a un solo efecto 
En la ciudad de ROJAS, a los {date.today().strftime("%d/%m/%Y")}.

LA UNIDAD HA SIDO REVISADA Y ACEPTADA EN CONFORMIDAD.
"""

            boleto.save()

            # Regenerar PDF
            try:
                if boleto.pdf:
                    boleto.pdf.delete(save=False)
                pdf_file = generar_boleto_pdf_desde_html(request, boleto)
                boleto.pdf.save(
                    f"boleto_{boleto.numero}.pdf",
                    pdf_file,
                    save=True
                )
                messages.success(request, "✅ Boleto actualizado y PDF regenerado correctamente.")
            except Exception as e:
                print("❌ ERROR PDF BOLETO (edición):", e)
                messages.warning(request, "⚠️ Boleto actualizado, pero el PDF no pudo regenerarse.")

            return redirect("boletos:ver_boleto", boleto.id)

    else:
        form = EditarBoletoForm(
            instance=boleto,
            initial={
                "precio_numeros":   precio_numeros_inicial,
                "precio_letras":    precio_letras_inicial,
                "saldo_forma_pago": saldo_forma_pago_inicial,
            }
        )

    return render(
        request,
        "boletos/editar.html",
        {
            "form": form,
            "boleto": boleto,
        }
    )


# ==========================================================
# =======================  PAGARÉ  =========================
# ==========================================================

def lista_pagares(request):
    q = request.GET.get("q", "").strip()

    lotes = (
        PagareLote.objects
        .select_related("cliente")
        .order_by("-fecha_emision")
    )

    if q:
        lotes = lotes.filter(
            Q(cliente__nombre_completo__icontains=q) |
            Q(cliente__dni_cuit__icontains=q) |
            Q(beneficiario__icontains=q)
        )

    lotes_con_url = []
    for lote in lotes:
        pdf_url = None
        if lote.pdf:
            url = lote.pdf.url
            if 'cloudinary.com' in url:
                url = url + '?fl_attachment'
            pdf_url = url
        lote_dict = {
            'id': lote.id,
            'cliente': lote.cliente,
            'beneficiario': lote.beneficiario,
            'fecha_emision': lote.fecha_emision,
            'cantidad': lote.cantidad,
            'monto_total': lote.monto_total,
            'pdf_url': pdf_url
        }
        lotes_con_url.append(lote_dict)

    return render(
        request,
        "boletos/pagare/lista.html",
        {
            "lotes": lotes_con_url,
            "query": q,
        }
    )


def monto_en_letras_simple(monto) -> str:
    try:
        if monto is None:
            return ""
        if not isinstance(monto, Decimal):
            monto = Decimal(str(monto))
        return f"{monto:,.0f}".replace(",", ".")
    except Exception:
        return str(monto)


def _generar_pdf_lote_pagares_3_por_hoja(pagares):
    """PDF A4 vertical, 2 pagares por hoja uno debajo del otro."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    ancho, alto = A4
    AZUL = colors.HexColor("#002855")
    margen = 1.5 * cm
    mitad_y = alto / 2

    meses_es = ["","enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
    def fecha_letras(f): return f"{f.day} de {meses_es[f.month]} de {f.year}"

    def dibujar_pagare(c, pagare, y_top, y_bottom):
        x = margen
        w = ancho - 2 * margen
        y = y_top - 0.8 * cm
        cl = pagare.cliente

        # Header empresa
        c.setFont("Helvetica-Bold", 9); c.setFillColor(AZUL)
        c.drawString(x, y, "AMICHETTI AUTOMOTORES")
        c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#555555"))
        c.drawString(x + 5.5*cm, y, "Larrea 255, Rojas, Buenos Aires")
        y -= 0.5*cm

        # Linea separadora
        c.setStrokeColor(AZUL); c.setLineWidth(1)
        c.line(x, y, x + w, y); y -= 0.5*cm

        # Titulo + monto
        c.setFont("Helvetica-Bold", 14); c.setFillColor(AZUL)
        c.drawString(x, y, "PAGARE")
        monto_str = f"$ {pagare.monto:,.0f}".replace(",", ".")
        # Caja monto
        bw = 4.5*cm; bh = 1.0*cm
        bx = x + w - bw; by = y - 0.1*cm
        c.setStrokeColor(AZUL); c.setLineWidth(0.8)
        c.rect(bx, by, bw, bh)
        c.setFont("Helvetica", 6); c.setFillColor(AZUL)
        c.drawCentredString(bx + bw/2, by + 0.75*cm, "IMPORTE")
        c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.HexColor("#059669"))
        c.drawCentredString(bx + bw/2, by + 0.2*cm, monto_str)
        y -= 0.5*cm

        # Numero y fechas
        venc_str = pagare.fecha_vencimiento.strftime("%d/%m/%Y") if pagare.fecha_vencimiento else "A la vista"
        c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#6b7280"))
        c.drawString(x, y, f"N {pagare.numero}  Lugar: {pagare.lugar_emision}  Fecha de emision: {pagare.fecha_emision.strftime('%d/%m/%Y')}")
        y -= 0.5*cm

        # Cuerpo legal
        c.setFont("Helvetica", 7.5); c.setFillColor(colors.black)
        venc_letras = fecha_letras(pagare.fecha_vencimiento) if pagare.fecha_vencimiento else "pagadero a la vista"
        texto = (
            f"Debo/Debemos y pagare/pagaremos mancomunada y solidariamente SIN PROTESTO "
            f"(Art. 50 D. Ley 5965/63), a la orden de {pagare.beneficiario.upper()}, "
            f"la suma de PESOS {pagare.monto:,.0f} ($ {monto_str}), "
            f"en {pagare.lugar_emision} el dia {venc_letras}. "
            f"En caso de mora el deudor pagara intereses punitorios. "
            f"El deudor constituye domicilio especial en {cl.direccion or pagare.lugar_emision} "
            f"y renuncia a los fueros que pudieran corresponderle."
        )

        y_firma = y_bottom + 2.2*cm
        palabras = texto.split(" "); linea = ""
        for p in palabras:
            prueba = linea + p + " "
            if c.stringWidth(prueba, "Helvetica", 7.5) > w:
                if y - 0.38*cm > y_firma:
                    c.drawString(x, y, linea.rstrip()); y -= 0.38*cm
                linea = p + " "
            else:
                linea = prueba
        if linea and y > y_firma:
            c.drawString(x, y, linea.rstrip()); y -= 0.38*cm

        y -= 0.2*cm

        # Datos deudor
        c.setFont("Helvetica-Bold", 7.5); c.setFillColor(AZUL)
        c.drawString(x, y, "El presente pagare es librado por:")
        y -= 0.38*cm
        c.setFont("Helvetica", 7.5); c.setFillColor(colors.black)
        c.drawString(x, y, f"{cl.nombre_completo.upper()}, DNI/CUIT {cl.dni_cuit or ''}, con domicilio en {cl.direccion or ''}")
        y -= 0.5*cm

        # Firmas
        firma_y = y_bottom + 1.0*cm
        c.setStrokeColor(colors.black); c.setLineWidth(0.5)
        # Firma deudor
        c.line(x, firma_y, x + w*0.35, firma_y)
        c.setFont("Helvetica", 6.5); c.setFillColor(colors.HexColor("#555555"))
        c.drawString(x, firma_y - 0.3*cm, "FIRMA DEL DEUDOR")
        c.drawString(x, firma_y - 0.55*cm, cl.nombre_completo.upper()[:35])
        c.drawString(x, firma_y - 0.78*cm, f"DNI: {cl.dni_cuit or ''}")

        # Caja vencimiento
        vbw = 3*cm; vbh = 1.1*cm
        vbx = x + w/2 - vbw/2
        vby = y_bottom + 0.3*cm
        c.setStrokeColor(AZUL); c.setLineWidth(0.8)
        c.rect(vbx, vby, vbw, vbh)
        c.setFont("Helvetica-Bold", 6.5); c.setFillColor(AZUL)
        c.drawCentredString(vbx + vbw/2, vby + 0.78*cm, "VENCE EL")
        c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.black)
        c.drawCentredString(vbx + vbw/2, vby + 0.25*cm, venc_str)

        # Aclaracion
        c.setStrokeColor(colors.black); c.setLineWidth(0.5)
        c.line(x + w*0.65, firma_y, x + w, firma_y)
        c.setFont("Helvetica", 6.5); c.setFillColor(colors.HexColor("#555555"))
        c.drawString(x + w*0.65, firma_y - 0.3*cm, "ACLARACION")

    def linea_corte(c, y):
        c.setStrokeColor(colors.HexColor("#999999"))
        c.setDash(4, 4); c.setLineWidth(0.6)
        c.line(margen, y, ancho - margen, y)
        c.setDash()

    i = 0
    while i < len(pagares):
        # Pagare superior
        dibujar_pagare(c, pagares[i], alto, mitad_y)
        # Linea de corte
        linea_corte(c, mitad_y)
        # Pagare inferior
        if i + 1 < len(pagares):
            dibujar_pagare(c, pagares[i+1], mitad_y, 0)
        c.showPage()
        i += 2

    c.save(); buf.seek(0)
    return buf.getvalue()


# ====================================
# CREAR PAGARÉS + PDF
# ====================================
def crear_pagares(request):
    if request.method == "POST":
        request.session.pop("generando_pagares", None)

        try:
            import traceback as _tb
            cliente = get_object_or_404(
                Cliente,
                id=request.POST.get("cliente")
            )

            beneficiario = (
                request.POST.get("beneficiario")
                or "AMICHETTI HUGO ALBERTO"
            )

            lugar_emision = (
                request.POST.get("lugar_emision")
                or "Rojas"
            )

            fecha_emision = (
                date.fromisoformat(request.POST.get("fecha_emision"))
                if request.POST.get("fecha_emision")
                else date.today()
            )

            cantidad = int(request.POST.get("cantidad", 1))

            lote = PagareLote.objects.create(
                cliente=cliente,
                beneficiario=beneficiario,
                lugar_emision=lugar_emision,
                fecha_emision=fecha_emision,
                cantidad=cantidad,
                monto_total=Decimal("0.00"),
            )

            ultimo = (
                Pagare.objects
                .aggregate(max_num=Max("numero"))
                .get("max_num")
                or 0
            )

            pagares = []
            monto_total = Decimal("0.00")

            for i in range(1, cantidad + 1):
                monto = Decimal(
                    request.POST.get(f"monto_{i}", "0")
                )

                fecha_v = request.POST.get(f"fecha_vencimiento_{i}")
                fecha_v = (
                    date.fromisoformat(fecha_v)
                    if fecha_v else None
                )

                pagare = Pagare.objects.create(
                    lote=lote,
                    cliente=cliente,
                    numero=ultimo + i,
                    beneficiario=beneficiario,
                    monto=monto,
                    lugar_emision=lugar_emision,
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_v
                )

                pagares.append(pagare)
                monto_total += monto

            pdf_bytes = _generar_pdf_lote_pagares_3_por_hoja(pagares)

            if not pdf_bytes:
                raise ValueError("No se pudo generar el PDF del pagaré.")

            filename = (
                f"pagares_lote_{lote.id}_"
                f"{fecha_emision.isoformat()}.pdf"
            )

            lote.pdf.save(
                filename,
                ContentFile(pdf_bytes),
                save=True
            )

            lote.monto_total = monto_total
            lote.cantidad = len(pagares)
            lote.save(update_fields=["monto_total", "cantidad"])

            messages.success(
                request,
                f"✅ Se creó el lote con {len(pagares)} pagarés en UN solo PDF."
            )

            return redirect("boletos:lista_pagares")

        except Exception as e:
            _tb.print_exc()
            messages.error(
                request,
                f"❌ Error al crear pagarés: {str(e)}"
            )
            return redirect("boletos:crear_pagares")

    return render(
        request,
        "boletos/pagare/crear.html",
        {"form": CrearPagareLoteForm()}
    )


# ====================================
# VER PAGARÉ
# ====================================
def ver_pagare(request, pagare_id):
    pagare = get_object_or_404(Pagare, id=pagare_id)
    return render(
        request,
        "boletos/pagare/ver.html",
        {"pagare": pagare}
    )


# ====================================
# PDF PAGARÉ INDIVIDUAL
# ====================================
def pagare_pdf(request, pagare_id):
    pagare = get_object_or_404(Pagare, id=pagare_id)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    azul = colors.HexColor("#002855")
    y = A4[1] - 2.2 * cm

    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(azul)
    c.drawString(2 * cm, y, "PAGARÉ")

    y -= 1 * cm
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Nº {pagare.numero}")

    y -= 1 * cm

    cliente = pagare.cliente
    venc = pagare.fecha_vencimiento.strftime("%d/%m/%Y") if pagare.fecha_vencimiento else "Pagadero a la vista"

    texto = [
        "PAGARÉ SIN PROTESTO A LA ORDEN DE AMICHETTI HUGO ALBERTO",
        "",
        f"Monto: $ {pagare.monto:,.2f}",
        f"Lugar y fecha de emisión: {pagare.lugar_emision}, {pagare.fecha_emision.strftime('%d/%m/%Y')}",
        f"Fecha de vencimiento: {venc}",
        "",
        f"Deudor: {cliente.nombre_completo}",
        f"DNI/CUIT: {cliente.dni_cuit or ''}",
        f"Domicilio: {cliente.direccion or ''}",
        "",
        "Firma: ________________________________",
    ]

    for t in texto:
        c.drawString(2 * cm, y, t)
        y -= 0.7 * cm

    c.showPage()
    c.save()

    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type="application/pdf")




# ====================================
# DESCARGAR PDF LOTE ON-DEMAND
# ====================================
def descargar_pdf_lote(request, lote_id):
    lote = get_object_or_404(PagareLote, id=lote_id)
    pagares = list(lote.pagares.all().order_by('numero'))
    
    pdf_bytes = _generar_pdf_lote_pagares_3_por_hoja(pagares)
    
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pagares_lote_{lote.id}.pdf"'
    return response

# ====================================
# VER LOTE DE PAGARÉS
# ====================================
def ver_lote(request, lote_id):
    lote = get_object_or_404(PagareLote, id=lote_id)
    pagares = lote.pagares.all().order_by('numero')
    pdf_url = None
    if lote.pdf:
        url = lote.pdf.url
        if 'cloudinary.com' in url:
            url = url.replace('/image/upload/', '/raw/upload/')
            if '?' not in url:
                url = url + '?fl_attachment'
        pdf_url = url
    return render(
        request,
        'boletos/pagare/lote_detalle.html',
        {'lote': lote, 'pagares': pagares, 'pdf_url': pdf_url}
    )


# ====================================
# ELIMINAR LOTE DE PAGARÉS
# ====================================
def eliminar_lote(request, lote_id):
    lote = get_object_or_404(PagareLote, id=lote_id)
    if request.method == 'POST':
        if lote.pdf:
            try:
                lote.pdf.delete(save=False)
            except Exception:
                pass
        lote.delete()
        messages.success(request, 'Lote de pagarés eliminado correctamente.')
        return redirect('boletos:lista_pagares')
    return render(request, 'boletos/pagare/eliminar_lote.html', {'lote': lote})
