import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Max, Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.conf import settings

logger = logging.getLogger(__name__)
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

from .models import BoletoCompraventa, Pagare, PagareLote, Reserva, EntregaDocumentacion
from .forms import CrearBoletoForm, CrearPagareLoteForm, ReservaForm, EntregaDocumentacionForm
from clientes.models import Cliente
from cuentas.models import CuentaCorriente


# ====================================
# HELPER: símbolo de moneda
# ====================================
def _simbolo_moneda(moneda):
    return 'U$S' if moneda == 'USD' else '$'


# ====================================
# HELPER: construir texto del boleto
# ====================================
def _construir_texto_boleto(cliente, vehiculo, f, moneda='ARS'):
    marca   = vehiculo.marca   if vehiculo else f.get('marca', '')
    modelo  = vehiculo.modelo  if vehiculo else f.get('modelo', '')
    anio    = vehiculo.anio    if vehiculo else f.get('anio', '')
    dominio = vehiculo.dominio if vehiculo else f.get('patente', '')

    ficha  = getattr(vehiculo, 'ficha', None) if vehiculo else None
    motor  = f.get('motor') or (getattr(ficha, 'numero_motor',  '') if ficha else '')
    chasis = f.get('chasis') or (getattr(ficha, 'numero_chasis', '') if ficha else '')

    precio_numeros   = f.get('precio_numeros', '')
    precio_letras    = f.get('precio_letras', '')
    saldo_forma_pago = f.get('saldo_forma_pago', '')
    domicilio_legal  = f.get('domicilio_legal', '') or (cliente.direccion or 'LARREA 255')
    compania_seguro  = f.get('compania_seguro', '')
    nota             = f.get('nota', '')

    simbolo      = _simbolo_moneda(moneda)
    moneda_texto = 'DÓLARES' if moneda == 'USD' else 'PESOS'

    hoy      = date.today()
    dia      = hoy.strftime('%d')
    mes      = hoy.strftime('%m')
    anio_hoy = hoy.strftime('%Y')

    texto = f"""Entre el/los Señor/es AMICHETTI HUGO ALBERTO por una parte como vendedor y el/los señor/es {cliente.nombre_completo} por la otra parte como comprador, convienen celebrar el presente boleto de acuerdo a las clausulas siguientes:
1° - El/los Señor/es AMICHETTI HUGO ALBERTO vende/n al/los Señor/es {cliente.nombre_completo} Un AUTOMOTOR Marca {marca} Modelo {modelo} Año {anio} Motor {motor} Chasis {chasis} Patente {dominio} en el estado que se encuentra, y que el comprador ha revisado y Controlando las numeraciones del motor, chasis, dominio y acepta de conformidad.
2° - El vendedor entrega en este acto toda la documentación referente al vehiculo y el comprador se obliga a realizar la respectiva transferencia dentro de los (30) treinta días a partir de la fecha, siendo a su cargo todo tramite que deba realizar y ante quien corresponda, eximiendo al vendedor de toda responsabilidad en lo referente a la transferencia o patentamiento.
3° - Los gastos que demande la transferencia del vehiculo en el orden nacional, provincial, municipal o de cualquier otro orden serán abonados por el comprador, y lo correspondiente a la ley 21.432/976.-
4° - El comprador deberá asegurar el automotor contra todo riesgo en la CIA {compania_seguro} dentro de los dos días de la fecha del presente boleto, siendo el endoso a favor del vendedor.-
5° - El comprador no podrá vender el vehiculo sin autorización expresa del vendedor hasta no haber abonado la totalidad de la deuda.-
6° - La falta de cumplimiento de cualquiera de las cláusulas del presente contrato autoriza al vendedor a solicitar el inmediato secuestro del vehiculo, renunciando el comprador a toda defensa en juicio.
7° - El vendedor podrá optar para el caso en el que el comprador se constituya en mora de alguna de las cuotas, por pedir el secuestro judicial de la unidad vendida, constituyendo el comprador para el caso de iniciársele acción judicial, domicilio legal en la calle {domicilio_legal}. Que asimismo y también para el caso de promover acción judicial, queda facultado el vendedor a nombrar martillero, comprometiéndose el comprador a no poner otra excepción que la de pago y renunciando expresamente a la facultad de apelar la resolución judicial dictada.
8° - Todos los gastos que origine cualquier acción judicial, que se iniciara, serán a cargo del comprador.
9° - El precio total de la unidad es de {simbolo} {precio_numeros} ({precio_letras} {moneda_texto}), quedando un saldo conforme la siguiente modalidad de pago: {saldo_forma_pago}
10° - La mora en el pago de todas las cuotas convenidas como saldo de precio se producirá por el mero vencimiento de una de ellas, sin necesidad de interpelación judicial o extra judicial de ninguna naturaleza, al producirse dicha mora el deudor perderá automáticamente a favor del vendedor todo lo abonado hasta esa fecha y la operación quedará rescindida, obligándose al comprador a devolver el vehículo en ese mismo momento. De no hacerlo así, pagará una multa diaria de acuerdo a los daños y perjuicios ocasionados al vendedor más toda otra indemnización que por ley correspondiere, pudiendo los vendedores a partir de ese momento disponer del vehículo arriba citado. Se deja perfectamente aclarado que este recibo es provisorio, debiendo el comprador gestionar directamente ante el titular o ante quien corresponda la transferencia del vehículo arriba citado.-
11° - El comprador pagará el 3% para gastos de prenda y el 1% para sellado. El comprador se hace responsable civil y criminalmente ante quien corresponda de los daños que ocasionara con este vehículo a partir de la fecha. En fe de cual se firman dos ejemplares de un mismo tenor y a un solo efecto en la ciudad de ROJAS a los {dia} días del mes de {mes} de {anio_hoy}.-"""

    if nota:
        texto += f"\nNota: {nota}"

    return texto


# ====================================
# HELPER: contexto compartido para boleto
# ====================================
def _contexto_boleto(boleto):
    texto_boleto = re.sub(
        r"\n\s*\n+", "\n", (boleto.texto_final or "").strip()
    )
    clausulas = [p.strip() for p in texto_boleto.split("\n") if p.strip()]
    nota = ""
    if "Nota:" in (boleto.texto_final or ""):
        nota = boleto.texto_final.split("Nota:")[-1].strip()

    cliente = boleto.cliente
    nombre_completo = (cliente.nombre_completo or "").strip()
    partes = nombre_completo.split(" ", 1)

    return {
        "boleto": boleto,
        "clausulas": clausulas,
        "nota": nota,
        "vendedor": {
            "apellido": "AMICHETTI",
            "nombre": "HUGO ALBERTO",
            "direccion": "LARREA 255",
            "dni": "13814200",
        },
        "comprador": {
            "apellido": partes[0] if partes else "",
            "nombre": partes[1] if len(partes) > 1 else "",
            "direccion": cliente.direccion or "",
            "dni": cliente.dni_cuit or "",
        },
    }


# ====================================
# PANEL DE BOLETOS
# ====================================
@login_required
def panel_boletos(request):
    return render(request, "boletos/panel.html")


# ====================================
# LISTA + BUSCADOR DE BOLETOS
# ====================================
@login_required
def lista_boletos(request):
    q = request.GET.get("q", "")
    boletos = BoletoCompraventa.objects.all()
    if q:
        boletos = boletos.filter(Q(texto_final__icontains=q))
    return render(request, "boletos/lista.html", {"boletos": boletos, "query": q})


# ====================================
# GENERAR PDF CON WEASYPRINT
# ====================================
@login_required
def generar_boleto_pdf_desde_html(request, boleto):
    from weasyprint import HTML
    ctx = _contexto_boleto(boleto)
    html_string = render_to_string("boletos/boleto_pdf.html", ctx, request=request)
    buffer = BytesIO()
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(buffer)
    buffer.seek(0)
    return ContentFile(buffer.read())


# ====================================
# VER BOLETO (pantalla)
# ====================================
@login_required
def ver_boleto(request, boleto_id):
    boleto = get_object_or_404(BoletoCompraventa, id=boleto_id)
    ctx = _contexto_boleto(boleto)
    return render(request, "boletos/ver.html", ctx)


# ====================================
# IMPRIMIR BOLETO (página limpia, sin base.html)
# — soluciona el blanco en Safari y Chrome
# ====================================
@login_required
def imprimir_boleto(request, boleto_id):
    boleto = get_object_or_404(BoletoCompraventa, id=boleto_id)
    ctx = _contexto_boleto(boleto)
    return render(request, "boletos/boleto_pdf.html", ctx)


# ====================================
# ELIMINAR BOLETO
# ====================================
@login_required
def eliminar_boleto(request, boleto_id):
    boleto = get_object_or_404(BoletoCompraventa, id=boleto_id)
    if request.method == "POST":
        if boleto.pdf:
            try:
                boleto.pdf.delete(save=False)
            except Exception:
                pass
        boleto.delete()
        messages.success(request, "Boleto eliminado correctamente.")
        return redirect("boletos:lista")
    return redirect("boletos:ver_boleto", boleto_id=boleto_id)


# ====================================
# CREAR BOLETO
# ====================================
@login_required
def crear_boleto_manual(request):
    ultimo = BoletoCompraventa.objects.aggregate(numero_max=Max("numero"))["numero_max"] or 0
    numero = ultimo + 1

    if request.method == "POST":
        form = CrearBoletoForm(request.POST)
        if form.is_valid():
            f        = form.cleaned_data
            cliente  = f["cliente"]
            vehiculo = f.get("vehiculo")
            moneda   = f.get("moneda", "ARS")

            if not vehiculo:
                messages.error(request, "❌ Debe seleccionar un vehículo.")
                return render(request, "boletos/crear.html", {"form": form, "numero": numero})

            if not cliente or not cliente.activo:
                messages.error(request, "❌ Cliente inválido.")
                return render(request, "boletos/crear.html", {"form": form, "numero": numero})

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

            texto_final = _construir_texto_boleto(cliente, vehiculo, f, moneda)
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
                boleto.pdf.save(f"boleto_{boleto.numero}.pdf", pdf_file, save=True)
            except Exception as e:
                logger.error("Error generando PDF boleto: %s", e)
                messages.warning(request, "⚠️ El boleto se creó, pero el PDF no pudo generarse.")

            messages.success(request, "✅ Boleto generado correctamente")
            return redirect("boletos:ver_boleto", boleto.id)

    return render(request, "boletos/crear.html", {"form": CrearBoletoForm(), "numero": numero})


# ====================================
# EDITAR BOLETO
# ====================================
@login_required
def editar_boleto(request, boleto_id):
    boleto = get_object_or_404(BoletoCompraventa, id=boleto_id)
    from .forms import EditarBoletoForm

    precio_numeros_inicial   = ""
    precio_letras_inicial    = ""
    saldo_forma_pago_inicial = ""
    moneda_inicial           = "ARS"
    motor_inicial            = ""
    chasis_inicial           = ""

    if boleto.texto_final:
        if 'U$S' in boleto.texto_final or 'DÓLARES' in boleto.texto_final:
            moneda_inicial = 'USD'
        match_9 = re.search(
            r"9°.*?precio total.*?es de\s*[U$S$]*\s*(.*?)\((.*?)\),\s*quedando.*?modalidad de pago:\s*(.*?)(?=10°|\Z)",
            boleto.texto_final,
            re.DOTALL | re.IGNORECASE
        )
        if match_9:
            precio_numeros_inicial   = match_9.group(1).strip()
            precio_letras_inicial    = match_9.group(2).strip()
            saldo_forma_pago_inicial = match_9.group(3).strip()
        match_mc = re.search(
            r"\bMotor\s+(\S.*?)\s+Chasis\s+(\S.*?)\s+Patente",
            boleto.texto_final,
        )
        if match_mc:
            motor_inicial  = match_mc.group(1).strip()
            chasis_inicial = match_mc.group(2).strip()

    if not motor_inicial and boleto.vehiculo:
        ficha = getattr(boleto.vehiculo, "ficha", None)
        motor_inicial  = getattr(ficha, "numero_motor", "")  or ""
        chasis_inicial = getattr(ficha, "numero_chasis", "") or ""

    if request.method == "POST":
        form = EditarBoletoForm(request.POST, instance=boleto)
        if form.is_valid():
            boleto   = form.save(commit=False)
            cliente  = boleto.cliente
            vehiculo = boleto.vehiculo
            moneda   = form.cleaned_data.get("moneda", "ARS")
            boleto.texto_final = _construir_texto_boleto(cliente, vehiculo, form.cleaned_data, moneda)
            boleto.save()
            try:
                if boleto.pdf:
                    boleto.pdf.delete(save=False)
                pdf_file = generar_boleto_pdf_desde_html(request, boleto)
                boleto.pdf.save(f"boleto_{boleto.numero}.pdf", pdf_file, save=True)
                messages.success(request, "✅ Boleto actualizado y PDF regenerado correctamente.")
            except Exception as e:
                logger.error("Error regenerando PDF boleto (edicion): %s", e)
                messages.warning(request, "⚠️ Boleto actualizado, pero el PDF no pudo regenerarse.")
            return redirect("boletos:ver_boleto", boleto.id)
    else:
        form = EditarBoletoForm(
            instance=boleto,
            initial={
                "moneda":           moneda_inicial,
                "precio_numeros":   precio_numeros_inicial,
                "precio_letras":    precio_letras_inicial,
                "saldo_forma_pago": saldo_forma_pago_inicial,
                "motor":            motor_inicial,
                "chasis":           chasis_inicial,
            }
        )

    return render(request, "boletos/editar.html", {"form": form, "boleto": boleto})


# ==========================================================
# =======================  PAGARÉ  =========================
# ==========================================================

@login_required
def lista_pagares(request):
    q = request.GET.get("q", "").strip()
    lotes = PagareLote.objects.select_related("cliente").order_by("-fecha_emision")
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
        lotes_con_url.append({
            'id': lote.id,
            'cliente': lote.cliente,
            'beneficiario': lote.beneficiario,
            'fecha_emision': lote.fecha_emision,
            'cantidad': lote.cantidad,
            'monto_total': lote.monto_total,
            'pdf_url': pdf_url
        })
    return render(request, "boletos/pagare/lista.html", {"lotes": lotes_con_url, "query": q})


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

        c.setFont("Helvetica-Bold", 9); c.setFillColor(AZUL)
        c.drawString(x, y, "AMICHETTI AUTOMOTORES")
        c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#555555"))
        c.drawString(x + 5.5*cm, y, "Larrea 255, Rojas, Buenos Aires")
        y -= 0.5*cm

        c.setStrokeColor(AZUL); c.setLineWidth(1)
        c.line(x, y, x + w, y); y -= 0.5*cm

        c.setFont("Helvetica-Bold", 14); c.setFillColor(AZUL)
        c.drawString(x, y, "PAGARE")
        monto_str = f"$ {pagare.monto:,.0f}".replace(",", ".")
        bw = 4.5*cm; bh = 1.0*cm
        bx = x + w - bw; by = y - 0.1*cm
        c.setStrokeColor(AZUL); c.setLineWidth(0.8)
        c.rect(bx, by, bw, bh)
        c.setFont("Helvetica", 6); c.setFillColor(AZUL)
        c.drawCentredString(bx + bw/2, by + 0.75*cm, "IMPORTE")
        c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.HexColor("#059669"))
        c.drawCentredString(bx + bw/2, by + 0.2*cm, monto_str)
        y -= 0.5*cm

        venc_str = pagare.fecha_vencimiento.strftime("%d/%m/%Y") if pagare.fecha_vencimiento else "A la vista"
        c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#6b7280"))
        c.drawString(x, y, f"N {pagare.numero}  Lugar: {pagare.lugar_emision}  Fecha de emision: {pagare.fecha_emision.strftime('%d/%m/%Y')}")
        y -= 0.5*cm

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
        c.setFont("Helvetica-Bold", 7.5); c.setFillColor(AZUL)
        c.drawString(x, y, "El presente pagare es librado por:")
        y -= 0.38*cm
        c.setFont("Helvetica", 7.5); c.setFillColor(colors.black)
        c.drawString(x, y, f"{cl.nombre_completo.upper()}, DNI/CUIT {cl.dni_cuit or ''}, con domicilio en {cl.direccion or ''}")
        y -= 0.5*cm

        firma_y = y_bottom + 1.0*cm
        c.setStrokeColor(colors.black); c.setLineWidth(0.5)
        c.line(x, firma_y, x + w*0.35, firma_y)
        c.setFont("Helvetica", 6.5); c.setFillColor(colors.HexColor("#555555"))
        c.drawString(x, firma_y - 0.3*cm, "FIRMA DEL DEUDOR")
        c.drawString(x, firma_y - 0.55*cm, cl.nombre_completo.upper()[:35])
        c.drawString(x, firma_y - 0.78*cm, f"DNI: {cl.dni_cuit or ''}")

        vbw = 3*cm; vbh = 1.1*cm
        vbx = x + w/2 - vbw/2
        vby = y_bottom + 0.3*cm
        c.setStrokeColor(AZUL); c.setLineWidth(0.8)
        c.rect(vbx, vby, vbw, vbh)
        c.setFont("Helvetica-Bold", 6.5); c.setFillColor(AZUL)
        c.drawCentredString(vbx + vbw/2, vby + 0.78*cm, "VENCE EL")
        c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.black)
        c.drawCentredString(vbx + vbw/2, vby + 0.25*cm, venc_str)

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
        dibujar_pagare(c, pagares[i], alto, mitad_y)
        linea_corte(c, mitad_y)
        if i + 1 < len(pagares):
            dibujar_pagare(c, pagares[i+1], mitad_y, 0)
        c.showPage()
        i += 2

    c.save(); buf.seek(0)
    return buf.getvalue()


# ====================================
# CREAR PAGARÉS + PDF
# ====================================
@login_required
def crear_pagares(request):
    if request.method == "POST":
        request.session.pop("generando_pagares", None)
        try:
            import traceback as _tb
            cliente = get_object_or_404(Cliente, id=request.POST.get("cliente"))
            beneficiario  = request.POST.get("beneficiario") or "AMICHETTI HUGO ALBERTO"
            lugar_emision = request.POST.get("lugar_emision") or "Rojas"
            try:
                fecha_emision = (
                    date.fromisoformat(request.POST.get("fecha_emision"))
                    if request.POST.get("fecha_emision") else date.today()
                )
            except ValueError:
                fecha_emision = date.today()
            cantidad = int(request.POST.get("cantidad", 1))

            lote = PagareLote.objects.create(
                cliente=cliente, beneficiario=beneficiario,
                lugar_emision=lugar_emision, fecha_emision=fecha_emision,
                cantidad=cantidad, monto_total=Decimal("0.00"),
            )

            ultimo = Pagare.objects.aggregate(max_num=Max("numero")).get("max_num") or 0
            pagares = []
            monto_total = Decimal("0.00")

            for i in range(1, cantidad + 1):
                monto   = Decimal(request.POST.get(f"monto_{i}", "0"))
                fecha_v = request.POST.get(f"fecha_vencimiento_{i}")
                try:
                    fecha_v = date.fromisoformat(fecha_v) if fecha_v else None
                except ValueError:
                    fecha_v = None
                pagare  = Pagare.objects.create(
                    lote=lote, cliente=cliente, numero=ultimo + i,
                    beneficiario=beneficiario, monto=monto,
                    lugar_emision=lugar_emision, fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_v
                )
                pagares.append(pagare)
                monto_total += monto

            pdf_bytes = _generar_pdf_lote_pagares_3_por_hoja(pagares)
            if not pdf_bytes:
                raise ValueError("No se pudo generar el PDF del pagaré.")

            filename = f"pagares_lote_{lote.id}_{fecha_emision.isoformat()}.pdf"
            lote.pdf.save(filename, ContentFile(pdf_bytes), save=True)
            lote.monto_total = monto_total
            lote.cantidad = len(pagares)
            lote.save(update_fields=["monto_total", "cantidad"])

            messages.success(request, f"✅ Se creó el lote con {len(pagares)} pagarés en UN solo PDF.")
            return redirect("boletos:lista_pagares")

        except Exception as e:
            _tb.print_exc()
            messages.error(request, f"❌ Error al crear pagarés: {str(e)}")
            return redirect("boletos:crear_pagares")

    return render(request, "boletos/pagare/crear.html", {"form": CrearPagareLoteForm()})


# ====================================
# VER PAGARÉ
# ====================================
@login_required
def ver_pagare(request, pagare_id):
    pagare = get_object_or_404(Pagare, id=pagare_id)
    return render(request, "boletos/pagare/ver.html", {"pagare": pagare})


# ====================================
# PDF PAGARÉ INDIVIDUAL
# ====================================
@login_required
def pagare_pdf(request, pagare_id):
    pagare = get_object_or_404(Pagare, id=pagare_id)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    azul = colors.HexColor("#002855")
    y = A4[1] - 2.2 * cm
    c.setFont("Helvetica-Bold", 18); c.setFillColor(azul)
    c.drawString(2 * cm, y, "PAGARÉ")
    y -= 1 * cm
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Nº {pagare.numero}")
    y -= 1 * cm
    cliente = pagare.cliente
    venc = pagare.fecha_vencimiento.strftime("%d/%m/%Y") if pagare.fecha_vencimiento else "Pagadero a la vista"
    for t in [
        "PAGARÉ SIN PROTESTO A LA ORDEN DE AMICHETTI HUGO ALBERTO", "",
        f"Monto: $ {pagare.monto:,.2f}",
        f"Lugar y fecha de emisión: {pagare.lugar_emision}, {pagare.fecha_emision.strftime('%d/%m/%Y')}",
        f"Fecha de vencimiento: {venc}", "",
        f"Deudor: {cliente.nombre_completo}",
        f"DNI/CUIT: {cliente.dni_cuit or ''}",
        f"Domicilio: {cliente.direccion or ''}", "",
        "Firma: ________________________________",
    ]:
        c.drawString(2 * cm, y, t); y -= 0.7 * cm
    c.showPage(); c.save()
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type="application/pdf")


# ====================================
# DESCARGAR PDF LOTE ON-DEMAND
# ====================================
@login_required
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
@login_required
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
    return render(request, 'boletos/pagare/lote_detalle.html', {'lote': lote, 'pagares': pagares, 'pdf_url': pdf_url})


# ====================================
# ELIMINAR LOTE DE PAGARÉS
# ====================================
@login_required
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


# ==========================================================
# ====================  RESERVAS  ==========================
# ==========================================================

# ────────────────────────────────────────────────────────
# HELPER: generar PDF de reserva con ReportLab
# (mismo estilo visual que los boletos)
# ────────────────────────────────────────────────────────
def _fmt_moneda(valor):
    if valor is None:
        return ""
    return f"$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _generar_pdf_reserva(reserva):
    buf = BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buf, pagesize=A4)

    ML = 2 * cm          # margen izquierdo
    MR = 2 * cm          # margen derecho
    CW = page_w - ML - MR  # ancho útil
    GRIS = colors.HexColor("#CCCCCC")
    NEGRO = colors.black

    y = page_h - 1.5 * cm

    # ── Encabezado ──────────────────────────────────────
    c.setFont("Helvetica-Bold", 13)
    c.drawString(ML, y, "AMICHETTI HUGO")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(page_w - MR, y, f"RESERVA N° {reserva.numero_reserva}")
    y -= 0.42 * cm
    c.setFont("Helvetica", 8)
    c.drawString(ML, y, "Av. Larrea n 255 · (2705) Rojas (B)  ·  Tel: 02475-465115  ·  hugoamichetti@speedy.com.ar")
    fecha_str = reserva.fecha_reserva.strftime("%d/%m/%Y") if reserva.fecha_reserva else date.today().strftime("%d/%m/%Y")
    c.drawRightString(page_w - MR, y, f"Fecha: {fecha_str}")
    y -= 0.5 * cm

    c.setStrokeColor(NEGRO); c.setLineWidth(1)
    c.line(ML, y, page_w - MR, y)
    y -= 0.4 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(page_w / 2, y, "FORMULARIO DE RESERVA DE VEHÍCULO")
    y -= 0.65 * cm

    # ── Helpers locales ──────────────────────────────────
    def sec_header(titulo):
        nonlocal y
        c.setFillColor(NEGRO)
        c.rect(ML, y - 0.08 * cm, CW, 0.48 * cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(ML + 0.2 * cm, y, titulo)
        c.setFillColor(NEGRO)
        y -= 0.62 * cm

    def linea_punt(x1, x2, yy):
        c.setStrokeColor(GRIS); c.setLineWidth(0.4); c.setDash(2, 3)
        c.line(x1, yy - 0.04 * cm, x2, yy - 0.04 * cm)
        c.setDash(); c.setStrokeColor(NEGRO)

    def campo(label, valor, x, ancho_label=3.5 * cm, ancho_total=None):
        nonlocal y
        at = ancho_total or CW
        c.setFont("Helvetica", 7.5)
        c.drawString(x, y, label)
        lx = x + ancho_label
        linea_punt(lx, x + at, y)
        if valor:
            c.setFont("Helvetica-Bold", 8)
            c.drawString(lx + 0.12 * cm, y, str(valor))

    def monto_box(label, valor):
        nonlocal y
        bw = 4 * cm
        bx = page_w - MR - bw
        c.setFont("Helvetica", 7.5)
        c.drawString(ML, y, label)
        c.setStrokeColor(GRIS); c.setLineWidth(0.5)
        c.rect(bx, y - 0.24 * cm, bw, 0.44 * cm, stroke=1, fill=0)
        c.setStrokeColor(NEGRO)
        if valor:
            c.setFont("Helvetica-Bold", 8)
            c.drawRightString(page_w - MR - 0.18 * cm, y, _fmt_moneda(valor))
        y -= 0.5 * cm

    # ── Datos del Solicitante ────────────────────────────
    sec_header("DATOS DEL SOLICITANTE")
    y -= 0.15 * cm
    campo("Apellido y Nombre o Razón Social:", reserva.apellido_nombre, ML, ancho_label=5.8 * cm)
    y -= 0.52 * cm
    campo("DNI:", reserva.dni, ML, ancho_label=0.8 * cm, ancho_total=4.2 * cm)
    campo("Domicilio:", reserva.domicilio, ML + 4.7 * cm, ancho_label=1.9 * cm, ancho_total=CW - 4.7 * cm)
    y -= 0.52 * cm
    campo("Teléfono:", reserva.telefono, ML, ancho_label=1.8 * cm, ancho_total=3.8 * cm)
    campo("CUIT:", reserva.cuit, ML + 4.3 * cm, ancho_label=1 * cm, ancho_total=3.5 * cm)
    campo("I.V.A.:", reserva.iva, ML + 8.5 * cm, ancho_label=1.1 * cm, ancho_total=CW - 8.5 * cm)
    y -= 0.7 * cm

    # ── Datos del Vehículo ───────────────────────────────
    sec_header("DATOS DEL VEHÍCULO QUE SOLICITA RESERVA")
    y -= 0.15 * cm
    campo("Marca:", reserva.marca, ML, ancho_label=1.2 * cm, ancho_total=3.8 * cm)
    campo("Modelo:", reserva.modelo, ML + 4.3 * cm, ancho_label=1.5 * cm, ancho_total=4.2 * cm)
    campo("Año:", reserva.anio, ML + 9.8 * cm, ancho_label=0.8 * cm, ancho_total=2 * cm)
    campo("Dominio:", reserva.dominio, ML + 12.4 * cm, ancho_label=1.6 * cm, ancho_total=CW - 12.4 * cm)
    y -= 0.52 * cm
    campo("Motor N°:", reserva.motor_nro, ML, ancho_label=1.7 * cm, ancho_total=5.5 * cm)
    campo("Chasis N°:", reserva.chasis_nro, ML + 6.5 * cm, ancho_label=1.8 * cm, ancho_total=CW - 6.5 * cm)
    y -= 0.7 * cm

    # ── Detalle de la Operación ──────────────────────────
    sec_header("DETALLE DE LA OPERACIÓN")
    y -= 0.15 * cm
    monto_box("Precio de Vehículo", reserva.precio_vehiculo)
    monto_box("Opcionales / Otros gastos", reserva.opcionales)
    c.setStrokeColor(NEGRO); c.setLineWidth(0.5)
    c.line(page_w - MR - 4 * cm, y + 0.1 * cm, page_w - MR, y + 0.1 * cm)
    y -= 0.1 * cm
    monto_box("TOTAL A PAGAR:", reserva.total_a_pagar)
    monto_box("SEÑA:", reserva.senia)
    y -= 0.2 * cm

    # ── Propuesta de Pago ────────────────────────────────
    sec_header("PROPUESTA DE PAGO")
    y -= 0.15 * cm
    monto_box("- Contado Efectivo:", reserva.contado_efectivo)
    monto_box("- A pagar contra la entrega de la unidad en efectivo:", reserva.pago_entrega)

    # Cheques
    c.setFont("Helvetica", 7.5); c.drawString(ML, y, "- CHEQUES:")
    if reserva.cheques:
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(ML + 2 * cm, y, str(reserva.cheques)[:90])
    linea_punt(ML + 2 * cm, page_w - MR, y)
    y -= 0.45 * cm
    linea_punt(ML, page_w - MR, y)
    y -= 0.42 * cm

    # Total propuesta
    bw = 4 * cm; bx = page_w - MR - bw
    c.setFont("Helvetica", 7.5); c.drawString(ML, y, "TOTAL:")
    c.setStrokeColor(GRIS); c.setLineWidth(0.5)
    c.rect(bx, y - 0.24 * cm, bw, 0.44 * cm, stroke=1, fill=0)
    c.setStrokeColor(NEGRO)
    if reserva.total_propuesta:
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(page_w - MR - 0.18 * cm, y, _fmt_moneda(reserva.total_propuesta))
    y -= 0.55 * cm

    # Crédito prendario
    check = "☑" if reserva.credito_prendario else "☐"
    c.setFont("Helvetica", 7.5)
    c.drawString(ML, y, f"{check}  Crédito prendario que autorizo a gestionar en la Entidad Financiera que determinen")
    y -= 0.45 * cm

    campo("- Otro concepto:", reserva.otro_concepto, ML, ancho_label=2.8 * cm)
    y -= 0.5 * cm

    # Cuotas
    c.setFont("Helvetica", 7.5)
    c.drawString(ML, y, "- En")
    linea_punt(ML + 0.5 * cm, ML + 2 * cm, y)
    if reserva.cant_cuotas:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(ML + 0.6 * cm, y, str(reserva.cant_cuotas))
    c.setFont("Helvetica", 7.5)
    c.drawString(ML + 2.1 * cm, y, "cuotas de Pesos")
    linea_punt(ML + 4.6 * cm, ML + 8.5 * cm, y)
    if reserva.valor_cuota:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(ML + 4.7 * cm, y, _fmt_moneda(reserva.valor_cuota))
    c.setFont("Helvetica", 7.5)
    c.drawString(ML + 8.6 * cm, y, "al día")
    linea_punt(ML + 9.5 * cm, ML + 11.5 * cm, y)
    if reserva.dia_cuota:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(ML + 9.6 * cm, y, reserva.dia_cuota)
    # caja monto cuota derecha
    c.setStrokeColor(GRIS); c.setLineWidth(0.5)
    c.rect(page_w - MR - 4 * cm, y - 0.24 * cm, 4 * cm, 0.44 * cm, stroke=1, fill=0)
    c.setStrokeColor(NEGRO)
    y -= 0.7 * cm

    # ── Vehículo Usado en Parte de Pago ─────────────────
    sec_header("VEHÍCULO USADO QUE PROPONGO ENTREGAR EN PARTE DE PAGO")
    y -= 0.15 * cm
    campo("Marca:", reserva.permuta_marca, ML, ancho_label=1.2 * cm, ancho_total=5.8 * cm)
    campo("Patente N°:", reserva.permuta_patente, ML + 6.5 * cm, ancho_label=2 * cm, ancho_total=CW - 6.5 * cm)
    y -= 0.52 * cm
    monto_box("En la suma de:", reserva.permuta_suma)
    monto_box("TOTAL:", reserva.permuta_total)
    y -= 0.2 * cm

    # ── Observaciones ────────────────────────────────────
    sec_header("OBSERVACIONES")
    y -= 0.15 * cm
    if reserva.observaciones:
        c.setFont("Helvetica", 8)
        c.drawString(ML, y, str(reserva.observaciones)[:200])
        y -= 0.42 * cm
    linea_punt(ML, page_w - MR, y); y -= 0.42 * cm
    linea_punt(ML, page_w - MR, y); y -= 0.6 * cm

    # ── Cláusula legal ───────────────────────────────────
    clausula = (
        "Sin perjuicio de las Condiciones Generales obrantes al dorso de la presente, que el solicitante declara conocer "
        "firmando de conformidad, se deja expresamente establecido, que esta reserva de compra no es vinculante para el "
        "Concesionario hasta tanto no sea aprobada y firmada por el representante legal; en consecuencia, hasta dicho "
        "momento, podrá ser rechazada en su totalidad y sin ninguna limitación, no otorgando dicho rechazo, derecho a "
        "reclamo y/o indemnización alguna por parte del Solicitante."
    )
    c.setFont("Helvetica", 6.5)
    linea_actual = ""
    for palabra in clausula.split():
        prueba = linea_actual + " " + palabra if linea_actual else palabra
        if c.stringWidth(prueba, "Helvetica", 6.5) < CW:
            linea_actual = prueba
        else:
            c.drawString(ML, y, linea_actual); y -= 0.3 * cm
            linea_actual = palabra
    if linea_actual:
        c.drawString(ML, y, linea_actual); y -= 0.3 * cm
    y -= 0.6 * cm

    # ── Firmas ───────────────────────────────────────────
    firma_y = max(y, 2.2 * cm)
    mitad = page_w / 2
    c.setStrokeColor(NEGRO); c.setLineWidth(0.5)
    c.line(ML, firma_y, mitad - 1 * cm, firma_y)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString((ML + mitad - 1 * cm) / 2, firma_y - 0.38 * cm, "REPRESENTANTE")
    c.line(mitad + 1 * cm, firma_y, page_w - MR, firma_y)
    c.drawCentredString((mitad + 1 * cm + page_w - MR) / 2, firma_y - 0.38 * cm, "FIRMA DE CONFORMIDAD DEL SOLICITANTE")

    c.save(); buf.seek(0)
    return buf.read()


# ────────────────────────────────────────────────────────
# LISTA DE RESERVAS
# ────────────────────────────────────────────────────────
@login_required
def lista_reservas(request):
    q = request.GET.get("q", "").strip()
    reservas = Reserva.objects.all()
    if q:
        reservas = reservas.filter(
            Q(apellido_nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo__icontains=q) |
            Q(numero_reserva__icontains=q) |
            Q(dni__icontains=q)
        )
    return render(request, "boletos/reservas/lista.html", {"reservas": reservas, "query": q})


# ────────────────────────────────────────────────────────
# CREAR RESERVA
# ────────────────────────────────────────────────────────
@login_required
def crear_reserva(request):
    if request.method == "POST":
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save()
            messages.success(request, f"✅ Reserva {reserva.numero_reserva} creada correctamente.")
            return redirect("boletos:ver_reserva", reserva_id=reserva.pk)
    else:
        form = ReservaForm()
    return render(request, "boletos/reservas/form.html", {
        "form": form,
        "titulo": "Nueva Reserva",
    })


# ────────────────────────────────────────────────────────
# VER RESERVA
# ────────────────────────────────────────────────────────
@login_required
def ver_reserva(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    return render(request, "boletos/reservas/ver.html", {"reserva": reserva})


# ────────────────────────────────────────────────────────
# EDITAR RESERVA
# ────────────────────────────────────────────────────────
@login_required
def editar_reserva(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    if request.method == "POST":
        form = ReservaForm(request.POST, instance=reserva)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Reserva {reserva.numero_reserva} actualizada.")
            return redirect("boletos:ver_reserva", reserva_id=reserva.pk)
    else:
        form = ReservaForm(instance=reserva)
    return render(request, "boletos/reservas/form.html", {
        "form": form,
        "titulo": f"Editar Reserva {reserva.numero_reserva}",
        "reserva": reserva,
    })


# ────────────────────────────────────────────────────────
# ELIMINAR RESERVA
# ────────────────────────────────────────────────────────
@login_required
def eliminar_reserva(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    if request.method == "POST":
        numero = reserva.numero_reserva
        reserva.delete()
        messages.success(request, f"Reserva {numero} eliminada.")
        return redirect("boletos:lista_reservas")
    return render(request, "boletos/reservas/confirmar_eliminar.html", {"reserva": reserva})


# ────────────────────────────────────────────────────────
# PDF RESERVA
# ────────────────────────────────────────────────────────
@login_required
def reserva_pdf(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    pdf_bytes = _generar_pdf_reserva(reserva)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="reserva_{reserva.numero_reserva}.pdf"'
    return response


# ====================================
# ENTREGA DE DOCUMENTACION - LISTA
# ====================================
@login_required
def lista_entregas(request):
    q = request.GET.get("q", "")
    entregas = EntregaDocumentacion.objects.all()
    if q:
        entregas = entregas.filter(
            Q(nombre_comprador__icontains=q)
            | Q(dominio__icontains=q)
            | Q(marca__icontains=q)
            | Q(modelo__icontains=q)
        )
    return render(request, "boletos/entregas/lista.html", {
        "entregas": entregas,
        "query": q,
    })


# ====================================
# ENTREGA DE DOCUMENTACION - CREAR
# ====================================
@login_required
def crear_entrega(request):
    from vehiculos.models import Vehiculo, FichaVehicular

    if request.method == "POST":
        form = EntregaDocumentacionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Entrega de documentacion registrada.")
            return redirect("boletos:lista_entregas")
    else:
        form = EntregaDocumentacionForm()

    vehiculos_json = []
    for v in Vehiculo.objects.all().order_by("-id"):
        ficha = getattr(v, "ficha", None)
        vehiculos_json.append({
            "id": v.id,
            "marca": v.marca,
            "modelo": v.modelo,
            "dominio": v.dominio,
            "anio": str(v.anio) if v.anio else "",
            "motor": ficha.numero_motor if ficha and ficha.numero_motor else "",
            "chasis": ficha.numero_chasis if ficha and ficha.numero_chasis else "",
        })

    import json
    return render(request, "boletos/entregas/form.html", {
        "form": form,
        "titulo": "Nueva Entrega de Documentacion",
        "vehiculos_json": json.dumps(vehiculos_json),
    })


# ====================================
# ENTREGA DE DOCUMENTACION - VER
# ====================================
@login_required
def ver_entrega(request, pk):
    entrega = get_object_or_404(EntregaDocumentacion, pk=pk)
    return render(request, "boletos/entregas/ver.html", {"entrega": entrega})


# ====================================
# ENTREGA DE DOCUMENTACION - ELIMINAR
# ====================================
@login_required
def eliminar_entrega(request, pk):
    entrega = get_object_or_404(EntregaDocumentacion, pk=pk)
    if request.method == "POST":
        entrega.delete()
        messages.success(request, "Entrega eliminada.")
        return redirect("boletos:lista_entregas")
    return render(request, "boletos/entregas/eliminar.html", {"entrega": entrega})


# ====================================
# ENTREGA DE DOCUMENTACION - PDF
# ====================================
@login_required
def entrega_pdf(request, pk):
    entrega = get_object_or_404(EntregaDocumentacion, pk=pk)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="entrega_{entrega.dominio}_{entrega.pk}.pdf"'
    )

    c = canvas.Canvas(response, pagesize=A4)
    w, h = A4

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, h - 2 * cm, "AMICHETTI AUTOMOTORES")
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, h - 2.6 * cm, "Rojas, Buenos Aires")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, h - 3.6 * cm, "RECIBO DE ENTREGA DE DOCUMENTACION")

    # Datos del vehiculo
    y = h - 4.8 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "DATOS DEL VEHICULO")
    y -= 0.6 * cm
    c.setFont("Helvetica", 9)

    datos_vehiculo = [
        f"Marca: {entrega.marca}",
        f"Modelo: {entrega.modelo}",
        f"Dominio: {entrega.dominio}",
        f"Anio: {entrega.anio or '-'}",
        f"Motor: {entrega.motor or '-'}",
        f"Chasis: {entrega.chasis or '-'}",
    ]
    for dato in datos_vehiculo:
        c.drawString(2.5 * cm, y, dato)
        y -= 0.45 * cm

    # Datos del comprador
    y -= 0.4 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "DATOS DEL COMPRADOR")
    y -= 0.6 * cm
    c.setFont("Helvetica", 9)

    datos_comprador = [
        f"Nombre: {entrega.nombre_comprador}",
        f"DNI: {entrega.dni_comprador or '-'}",
        f"Domicilio: {entrega.domicilio_comprador or '-'}",
        f"Telefono: {entrega.telefono_comprador or '-'}",
    ]
    for dato in datos_comprador:
        c.drawString(2.5 * cm, y, dato)
        y -= 0.45 * cm

    # Checklist
    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "DOCUMENTACION RECIBIDA")
    y -= 0.6 * cm
    c.setFont("Helvetica", 9)

    items = entrega.items_entregados()

    col1_x = 2.5 * cm
    col2_x = 10.5 * cm
    items_por_col = (len(items) + 1) // 2

    y_start = y
    for i, (nombre, valor) in enumerate(items):
        marca = "SI" if valor == "si" else "NO"
        texto = f"{nombre}: {marca}"

        if i < items_por_col:
            c.drawString(col1_x, y_start - (i * 0.45 * cm), texto)
        else:
            c.drawString(col2_x, y_start - ((i - items_por_col) * 0.45 * cm), texto)

    y = y_start - (items_por_col * 0.45 * cm) - 0.6 * cm

    # Observaciones
    if entrega.observaciones:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(2 * cm, y, "Observaciones:")
        y -= 0.4 * cm
        c.setFont("Helvetica", 8)
        for linea in entrega.observaciones.split("\n"):
            c.drawString(2.5 * cm, y, linea.strip())
            y -= 0.35 * cm

    # Fecha y firma
    y -= 1 * cm
    fecha_str = entrega.fecha.strftime("%d/%m/%Y") if entrega.fecha else ""
    hora_str = entrega.hora.strftime("%H:%M") if entrega.hora else ""
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, y, f"Fecha: {fecha_str}    Hora: {hora_str}")

    y -= 2 * cm
    c.line(2 * cm, y, 8 * cm, y)
    c.drawString(2 * cm, y - 0.4 * cm, "Firma del comprador")

    c.line(11 * cm, y, 17 * cm, y)
    c.drawString(11 * cm, y - 0.4 * cm, "Firma autorizada")

    y -= 0.8 * cm
    c.line(2 * cm, y, 8 * cm, y)
    c.drawString(2 * cm, y - 0.4 * cm, "Aclaracion")

    c.line(11 * cm, y, 17 * cm, y)
    c.drawString(11 * cm, y - 0.4 * cm, "Aclaracion")

    # Footer
    c.setFont("Helvetica", 7)
    c.drawCentredString(w / 2, 1.5 * cm, "Amichetti Automotores - Documento generado por sistema")

    c.showPage()
    c.save()
    return response
