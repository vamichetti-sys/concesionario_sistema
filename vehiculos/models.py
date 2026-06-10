from django.db import models
from decimal import Decimal
from django.apps import apps
from datetime import date


# ============================================================
# VEHICULO
# ============================================================
class Vehiculo(models.Model):
    ESTADOS = [
        ('stock', 'En stock'),
        ('temporal', 'Temporalmente no disponible'),
        ('vendido', 'Vendido'),
        ('reventa', 'En reventa'),
    ]

    UNIDAD_CHOICES = [
        ("HA", "Hamichetti"),
        ("VA", "Vamichetti"),
    ]

    unidad = models.CharField(
        max_length=2,
        choices=UNIDAD_CHOICES,
        default="HA",
        verbose_name="Unidad"
    )

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    # Sin unique a nivel BD: la unicidad de patentes reales se valida en el
    # formulario, pero permitimos varios "A DECLARAR" (vehículos 0km sin patente).
    dominio = models.CharField(max_length=15)

    anio = models.PositiveIntegerField("Año")
    kilometros = models.PositiveIntegerField(null=True, blank=True)

    precio = models.DecimalField(max_digits=12, decimal_places=2)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='stock'
    )

    es_0km = models.BooleanField(
        default=False,
        help_text="Indica si el vehículo es 0 km"
    )

    numero_carpeta = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Número de carpeta"
    )

    fecha_ingreso = models.DateField(
        "Fecha de ingreso",
        default=date.today,
        help_text="Fecha en que el vehículo ingresó al stock. Se completa automáticamente con la fecha de alta y se puede editar.",
    )

    # ======================================================
    # REPRESENTACIÓN
    # ======================================================
    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.dominio})"

    # ======================================================
    # PROPIEDADES DE VENTA (SE CONSERVAN TODAS)
    # ======================================================
    @property
    def tiene_venta(self):
        return hasattr(self, "venta")

    @property
    def tiene_venta_activa(self):
        return self.tiene_venta and self.venta.estado == "confirmada"

    @property
    def esta_vendido_correctamente(self):
        return self.estado == "vendido" and self.tiene_venta_activa

    # ======================================================
    # REGLA DE ELIMINACIÓN
    # ======================================================
    def puede_eliminarse(self):
        return not self.tiene_venta_activa

# ============================================================
# FICHA VEHICULAR COMPLETA
# ============================================================
class FichaVehicular(models.Model):

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="ficha"
    )

    numero_consignacion_factura = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    fecha_inscripcion_inicial = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de inscripción inicial"
    )


    # =========================
    # DATOS DEL TITULAR
    # =========================
    titular = models.CharField(max_length=150, blank=True, null=True)
    dni_titular = models.CharField(max_length=20, blank=True, null=True)
    cuit_cuil_dni = models.CharField(max_length=20, blank=True, null=True)
    estado_civil = models.CharField(max_length=50, blank=True, null=True)
    domicilio_titular = models.CharField(max_length=200, blank=True, null=True)
    email_contacto = models.EmailField(blank=True, null=True)
    contacto = models.CharField(max_length=100, blank=True, null=True)

    TIPO_INGRESO_CHOICES = [
        ('compra', 'Compra'),
        ('consignacion', 'Consignación'),
    ]

    tipo_ingreso = models.CharField(
        max_length=50,
        choices=TIPO_INGRESO_CHOICES,
        blank=True,
        null=True
    )

    vendedor = models.ForeignKey(
        "compraventa.Proveedor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehiculos",
        verbose_name="Agencia / Vendedor",
    )


   # =========================
    # DATOS DEL VEHÍCULO
    # =========================
    color = models.CharField(max_length=50, blank=True, null=True)
    combustible = models.CharField(max_length=50, blank=True, null=True)
    transmision = models.CharField(max_length=50, blank=True, null=True)
    numero_motor = models.CharField(max_length=100, blank=True, null=True)
    numero_chasis = models.CharField(max_length=100, blank=True, null=True)

    # (todo lo demás tuyo sigue igual)

    ESTADO_DOC = [
        ("tiene", "Tiene"),
        ("no_tiene", "No tiene"),
    ]

    # El Formulario 08 puede venir de distintos orígenes: el propio
    # concesionario, el proveedor que nos lo vendió, o de una reventa.
    F08_ORIGEN = [
        ("concesionario", "Concesionario"),
        ("proveedor", "Proveedor"),
        ("reventa", "Reventa"),
        ("no_tiene", "No tiene"),
    ]

    patentes_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    # ¿El vehículo adeuda patentes a la fecha de ingreso?
    PATENTES_ADEUDA = [("si", "Sí"), ("no", "No")]
    patentes_adeuda = models.CharField(
        "¿Adeuda patentes a la fecha de ingreso?",
        max_length=2, choices=PATENTES_ADEUDA, blank=True, null=True,
    )
    patentes_monto = models.DecimalField(
        "Monto adeudado de patentes",
        max_digits=12, decimal_places=2, blank=True, null=True,
    )
    patente_mensual = models.DecimalField(
        "Monto de la patente mensual",
        max_digits=12, decimal_places=2, blank=True, null=True,
    )
    patentes_vto1 = models.DateField(blank=True, null=True)
    patentes_vto2 = models.DateField(blank=True, null=True)
    patentes_vto3 = models.DateField(blank=True, null=True)
    patentes_vto4 = models.DateField(blank=True, null=True)
    patentes_vto5 = models.DateField(blank=True, null=True)

    f08_estado = models.CharField(max_length=20, choices=F08_ORIGEN, blank=True, null=True, verbose_name="Formulario 08 (origen)")
    cedula_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)

    # Estado registral del título (lo que informa el reporte de dominio)
    INFORME_CHOICES = [
        ("prendado", "Prendado"),
        ("sucesion", "Sucesión"),
        ("inhibido", "Inhibido"),
        ("embargado", "Embargado"),
    ]
    informe = models.CharField(max_length=20, choices=INFORME_CHOICES, blank=True, null=True, verbose_name="Informe")
    radicacion_anterior = models.CharField(max_length=200, blank=True, null=True, verbose_name="Radicación anterior")

    verificacion_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    verificacion_vencimiento = models.DateField(blank=True, null=True)

    autopartes_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    autopartes_turno = models.DateField(blank=True, null=True)
    autopartes_turno_obs = models.CharField(max_length=200, blank=True, null=True)

    vtv_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    vtv_turno = models.DateField(blank=True, null=True)
    vtv_vencimiento = models.DateField(blank=True, null=True)

    # =========================
    # TURNOS ADICIONALES
    # =========================
    verificacion_turno = models.DateField(blank=True, null=True, verbose_name="Turno verificación policial")
    gnc_turno = models.DateField(blank=True, null=True, verbose_name="Turno GNC")

    gasto_f08 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_informes = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_patentes = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_infracciones = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_verificacion = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_autopartes = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_vtv = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_r541 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_firmas = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    total_gastos = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    # ======================================================
    # GASTOS DE CONCESIONARIO (POST-INGRESO)
    # ======================================================
    gc_service = models.DecimalField("Service", max_digits=12, decimal_places=2, default=0)
    gc_mecanica = models.DecimalField("Mecanica", max_digits=12, decimal_places=2, default=0)
    gc_chapa_pintura = models.DecimalField("Chapa y pintura", max_digits=12, decimal_places=2, default=0)
    gc_tapizado = models.DecimalField("Tapizado", max_digits=12, decimal_places=2, default=0)
    gc_neumaticos = models.DecimalField("Neumaticos", max_digits=12, decimal_places=2, default=0)
    gc_vidrios = models.DecimalField("Vidrios", max_digits=12, decimal_places=2, default=0)
    gc_cerrajeria = models.DecimalField("Cerrajeria", max_digits=12, decimal_places=2, default=0)
    gc_lavado = models.DecimalField("Lavado / Pulido", max_digits=12, decimal_places=2, default=0)
    gc_gnc = models.DecimalField("GNC", max_digits=12, decimal_places=2, default=0)
    gc_grabado_autopartes = models.DecimalField("Grabado autopartes", max_digits=12, decimal_places=2, default=0)
    gc_vtv = models.DecimalField("VTV", max_digits=12, decimal_places=2, default=0)
    gc_verificacion = models.DecimalField("Verificacion policial", max_digits=12, decimal_places=2, default=0)
    gc_patentes = models.DecimalField("Patentes", max_digits=12, decimal_places=2, default=0)
    gc_otros = models.DecimalField("Otros", max_digits=12, decimal_places=2, default=0)

    observaciones = models.TextField(blank=True, null=True)
    # ======================================================
    # ACCESORIOS / CHECKLIST
    # ======================================================
    SI_NO = [
        ("si", "Sí"),
        ("no", "No"),
    ]

    duplicado_llave_estado = models.CharField(max_length=2, choices=SI_NO, blank=True, null=True)
    duplicado_llave_obs = models.CharField(max_length=200, blank=True, null=True)

    codigo_llave_estado = models.CharField(max_length=2, choices=SI_NO, blank=True, null=True)
    codigo_llave_obs = models.CharField(max_length=200, blank=True, null=True)

    codigo_radio_estado = models.CharField(max_length=2, choices=SI_NO, blank=True, null=True)
    codigo_radio_obs = models.CharField(max_length=200, blank=True, null=True)

    manuales_estado = models.CharField(max_length=2, choices=SI_NO, blank=True, null=True)
    manuales_obs = models.CharField(max_length=200, blank=True, null=True)

    oblea_gnc_estado = models.CharField(max_length=2, choices=SI_NO, blank=True, null=True)
    oblea_gnc_obs = models.CharField(max_length=200, blank=True, null=True)

    # ======================================================
    # 🆕 NUEVOS ÍTEMS SOLICITADOS (TÍTULO / CÉDULA / PRENDA)
    # ======================================================
    titulo_estado = models.CharField(
        max_length=2,
        choices=SI_NO,
        blank=True,
        null=True
    )
    titulo_obs = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    cedula_check_estado = models.CharField(
        max_length=2,
        choices=SI_NO,
        blank=True,
        null=True
    )
    cedula_check_obs = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    prenda_estado = models.CharField(
        max_length=2,
        choices=SI_NO,
        blank=True,
        null=True
    )
    prenda_obs = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )
    def __str__(self):
        return f"Ficha de {self.vehiculo.marca} {self.vehiculo.modelo}"

    # ======================================================
    # HELPERS EXISTENTES (NO SE TOCAN)
    # ======================================================
    def mapa_gastos_ingreso(self):
       return {
        "Formulario 08": self.gasto_f08,
        "Informes": self.gasto_informes,
        "Patentes": self.gasto_patentes,
        "Infracciones": self.gasto_infracciones,  # ← ESTA LÍNEA
        "Verificación": self.gasto_verificacion,
        "Autopartes": self.gasto_autopartes,
        "VTV": self.gasto_vtv,
        "R541": self.gasto_r541,
        "Firmas": self.gasto_firmas,
    }


    def total_pagado_por_concepto(self, concepto):
        # Mapeo entre los labels de mapa_gastos_ingreso y las keys cortas
        # con las que se guardan los pagos en PagoGastoIngreso
        LABEL_TO_KEY = {
            "Formulario 08": "f08",
            "Informes": "informes",
            "Patentes": "patentes",
            "Infracciones": "infracciones",
            "Verificación": "verificacion",
            "Autopartes": "autopartes",
            "VTV": "vtv",
            "R541": "r541",
            "Firmas": "firmas",
        }
        # Aceptar tanto label como key
        key_corta = LABEL_TO_KEY.get(concepto, concepto)

        # El saldo de la ficha es la deuda del vehículo CON EL ENTE. Solo lo
        # reducen los pagos en los que el ente quedó efectivamente pagado
        # (prov_directo, cli_directo, cli_adelanto, prov_reintegro). Los que
        # quedan "cli_concesion" (cliente me pagó, no pagué al ente) o
        # "pendiente" NO saldan el gasto con el ente.
        PagoGasto = apps.get_model("vehiculos", "PagoGastoIngreso")
        total = (
            PagoGasto.objects.filter(
                vehiculo=self.vehiculo,
                concepto__in=[concepto, key_corta],
                situacion__in=["prov_directo", "cli_directo", "cli_adelanto", "prov_reintegro"],
            ).aggregate(total=models.Sum("monto"))["total"]
        )
        return Decimal(total) if total else Decimal("0")

    def saldo_por_concepto(self, concepto):
        monto = self.mapa_gastos_ingreso().get(concepto) or Decimal("0")
        return Decimal(monto) - self.total_pagado_por_concepto(concepto)

    def saldo_total_gastos(self):
        total = Decimal("0")
        for concepto, monto in self.mapa_gastos_ingreso().items():
            if monto and Decimal(monto) > 0:
                total += self.saldo_por_concepto(concepto)
        return total

    def tiene_saldo_pendiente(self):
        for concepto, monto in self.mapa_gastos_ingreso().items():
            if monto and Decimal(monto) > 0 and self.saldo_por_concepto(concepto) > 0:
                return True
        return False
    
    # ======================================================
    # PROPERTY PARA SALDO DE GASTOS
    # ======================================================
    @property
    def saldo_gastos(self):
        """
        Saldo pendiente de gastos de ingreso.
        """
        return self.saldo_total_gastos()

    # ======================================================
    # COMPATIBILIDAD PARA PDF / TEMPLATES
    # ======================================================
    @property
    def fecha_inscripcion(self):
        return self.fecha_inscripcion_inicial

    @property
    def documento_titular(self):
        return self.dni_titular

    @property
    def numero_consignacion(self):
        return self.numero_consignacion_factura

   
    # ======================================================
    # ⚙️ AUTOMATIZACIÓN CONTABLE – PERMUTA
    # ======================================================
    def imputar_gastos_permuta_en_cuenta(self, cuenta):
        MovimientoCuenta = apps.get_model("cuentas", "MovimientoCuenta")

        if not cuenta:
            return

        gastos = {
            "Formulario 08": self.gasto_f08,
            "Informes": self.gasto_informes,
            "Patentes": self.gasto_patentes,
            "Infracciones": self.gasto_infracciones,
            "Verificación": self.gasto_verificacion,
            "Autopartes": self.gasto_autopartes,
            "VTV": self.gasto_vtv,
            "R541": self.gasto_r541,
            "Firmas": self.gasto_firmas,
        }

        for concepto, monto in gastos.items():
            if not monto or monto <= 0:
                continue

            existe = MovimientoCuenta.objects.filter(
                cuenta=cuenta,
                origen="permuta",
                vehiculo=self.vehiculo,
                descripcion__icontains=concepto,
            ).exists()

            if existe:
                continue

            MovimientoCuenta.objects.create(
                cuenta=cuenta,
                descripcion=f"{concepto} – Permuta {self.vehiculo}",
                tipo="debe",
                monto=Decimal(monto),
                origen="permuta",
                vehiculo=self.vehiculo
            )

        cuenta.recalcular_saldo()

# ============================================================
# PAGO DE GASTOS DE INGRESO
# ============================================================
class PagoGastoIngreso(models.Model):

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="pagos_gastos_ingreso"
    )

    concepto = models.CharField(max_length=100)
    fecha_pago = models.DateField()
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    observaciones = models.TextField(blank=True, null=True)
    creado = models.DateTimeField(auto_now_add=True)

    # A quién pertenece el gasto: lo determina el PROVEEDOR de la solapa
    # Titularidad (ficha.vendedor). Si hay proveedor → "proveedor"; si no →
    # "cliente". Se fija al registrar el pago.
    PERTENECE = [
        ("proveedor", "Proveedor"),
        ("cliente", "Cliente"),
    ]
    pertenece = models.CharField(max_length=10, choices=PERTENECE, default="cliente")

    # Situación del gasto (la elige el usuario al registrar el pago):
    #   Proveedor:  A) prov_directo   B) prov_reintegro
    #   Cliente:    1) cli_directo    2) cli_concesion
    #               3) cli_adelanto   4) pendiente
    SITUACION = [
        ("prov_directo",   "Proveedor pagó directo al ente (saldado)"),
        ("prov_reintegro", "Lo pagué yo, el proveedor me reintegra"),
        ("cli_directo",    "Cliente pagó directo al ente (saldado)"),
        ("cli_concesion",  "Cliente me pagó, todavía no pagué al ente"),
        ("cli_adelanto",   "Adelanté yo al ente, el cliente me debe"),
        ("pendiente",      "Nadie pagó todavía"),
    ]
    situacion = models.CharField(max_length=20, choices=SITUACION, default="pendiente")

    # Ente al que se le paga el trámite (VTV, registro, patentes…). Texto libre,
    # el formulario sugiere un valor inicial según el concepto.
    ente = models.CharField(max_length=120, blank=True)

    # Saldado: cierra el circuito y pasa a la sección "Saldadas".
    saldado = models.BooleanField(default=False)
    fecha_saldado = models.DateField(null=True, blank=True)

    # Referencias a registros creados en otros módulos (patrón IngresoFuturo),
    # para poder vincular y revertir sin descuadrar:
    movimiento_cuenta_id = models.PositiveIntegerField(null=True, blank=True)    # cuentas.MovimientoCuenta
    pago_futuro_id = models.PositiveIntegerField(null=True, blank=True)          # agenda_pagos.PagoFuturo
    reintegro_proveedor_id = models.PositiveIntegerField(null=True, blank=True)  # compraventa.ReintegroProveedor

    # ⚠️ LEGADO: reemplazado por situacion="cli_concesion". Se conserva durante
    # la transición y se eliminará al migrar la lógica de "Pago de gastos".
    mantiene_deuda_vehiculo = models.BooleanField(
        default=False,
        verbose_name="(legado) Sigue como deuda del vehículo",
    )

    class Meta:
        ordering = ["fecha_pago"]

    def __str__(self):
        return f"{self.vehiculo} - {self.concepto} - ${self.monto}"
# ============================================================
# CONFIGURACIÓN GLOBAL DE GASTOS DE INGRESO (PLANTILLA)
# ============================================================
class ConfiguracionGastosIngreso(models.Model):
    gasto_f08 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasto_informes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasto_patentes = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ✅ AGREGADO (CLAVE)
    gasto_infracciones = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    gasto_verificacion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasto_autopartes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasto_vtv = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasto_r541 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasto_firmas = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        # 🔒 FORZAMOS SIEMPRE PK = 1
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Configuración global de gastos de ingreso"


# ============================================================
# GASTO CONCESIONARIO (GASTOS POST-INGRESO POR VEHICULO)
# ============================================================
class GastoConcesionario(models.Model):
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="gastos_concesionario",
    )
    concepto = models.CharField(max_length=150)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fecha = models.DateField(auto_now_add=True)
    observaciones = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ["fecha"]
        verbose_name = "Gasto de concesionario"
        verbose_name_plural = "Gastos de concesionario"

    def __str__(self):
        return f"{self.concepto} – ${self.monto} – {self.vehiculo}"


# ============================================================
# FICHA TÉCNICA DEL VEHÍCULO
# ============================================================
class FichaTecnica(models.Model):
    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="ficha_tecnica",
    )

    # ── Mantenimiento ──────────────────────────────────────
    ultimo_service_fecha = models.DateField(blank=True, null=True, verbose_name="Último service – Fecha")
    ultimo_service_km = models.PositiveIntegerField(blank=True, null=True, verbose_name="Último service – Km")
    ultimo_cambio_aceite_fecha = models.DateField(blank=True, null=True, verbose_name="Cambio de aceite – Fecha")
    ultimo_cambio_aceite_km = models.PositiveIntegerField(blank=True, null=True, verbose_name="Cambio de aceite – Km")
    ultimo_cambio_correa_fecha = models.DateField(blank=True, null=True, verbose_name="Cambio de correa – Fecha")
    ultimo_cambio_correa_km = models.PositiveIntegerField(blank=True, null=True, verbose_name="Cambio de correa – Km")

    # ── Historia / Estado ──────────────────────────────────
    REPINTADO_CHOICES = [("no", "No"), ("parcial", "Parcial"), ("si", "Sí, completo")]
    repintado = models.CharField(max_length=10, choices=REPINTADO_CHOICES, blank=True, null=True, verbose_name="¿Repintado?")
    partes_repintadas = models.CharField(max_length=200, blank=True, null=True, verbose_name="Partes repintadas")

    CHOCADO_CHOICES = [("no", "No"), ("leve", "Leve"), ("importante", "Importante")]
    chocado = models.CharField(max_length=15, choices=CHOCADO_CHOICES, blank=True, null=True, verbose_name="¿Tuvo choque?")
    detalles_choque = models.TextField(blank=True, null=True, verbose_name="Detalles del choque")

    detalles_estado = models.TextField(blank=True, null=True, verbose_name="Detalles (rayones, golpes, particularidades)")
    no_funciona = models.TextField(blank=True, null=True, verbose_name="¿Algo no funciona?")

    # ── Cubiertas (cada una individual + auxilio) ──────────
    CUBIERTA_CHOICES = [
        ("nueva", "Nueva"),
        ("buena", "Buena"),
        ("regular", "Regular"),
        ("desgastada", "Desgastada"),
        ("cambiar", "A cambiar"),
    ]
    cubierta_di = models.CharField(max_length=15, choices=CUBIERTA_CHOICES, blank=True, null=True, verbose_name="Cubierta delantera izq.")
    cubierta_dd = models.CharField(max_length=15, choices=CUBIERTA_CHOICES, blank=True, null=True, verbose_name="Cubierta delantera der.")
    cubierta_ti = models.CharField(max_length=15, choices=CUBIERTA_CHOICES, blank=True, null=True, verbose_name="Cubierta trasera izq.")
    cubierta_td = models.CharField(max_length=15, choices=CUBIERTA_CHOICES, blank=True, null=True, verbose_name="Cubierta trasera der.")
    cubierta_auxilio = models.CharField(max_length=15, choices=CUBIERTA_CHOICES, blank=True, null=True, verbose_name="Rueda de auxilio")
    cubiertas_obs = models.TextField(blank=True, null=True, verbose_name="Observaciones cubiertas / auxilio")

    # ── Estado de sistemas y componentes ───────────────────
    ESTADO_GENERAL = [
        ("bueno", "Bueno"),
        ("regular", "Regular"),
        ("malo", "Malo"),
        ("no_funciona", "No funciona"),
    ]

    estado_motor = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Estado del motor")

    PERDIDA_FLUIDOS_CHOICES = [
        ("no", "No"),
        ("leve", "Leve"),
        ("importante", "Importante"),
    ]
    perdida_fluidos = models.CharField(max_length=15, choices=PERDIDA_FLUIDOS_CHOICES, blank=True, null=True, verbose_name="Pérdida de fluidos")
    perdida_fluidos_obs = models.CharField(max_length=200, blank=True, null=True, verbose_name="Detalle pérdida de fluidos")

    estado_suspension       = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Suspensión")
    estado_frenos           = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Sistema de frenos")
    estado_electrico        = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Sistema eléctrico")
    fallas_electrico_obs    = models.CharField(max_length=200, blank=True, null=True, verbose_name="Detalle de fallas eléctricas")
    estado_faros_opticas    = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Faros y ópticas")
    estado_tapizados        = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Tapizados")
    estado_volante          = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Desgaste del volante")
    estado_vidrios          = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Vidrios")
    estado_calefaccion      = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Calefacción")
    estado_aire             = models.CharField(max_length=15, choices=ESTADO_GENERAL, blank=True, null=True, verbose_name="Aire acondicionado")

    # ── Granizo ────────────────────────────────────────────
    GRANIZO_CHOICES = [
        ("no", "No"),
        ("leve", "Leve"),
        ("moderado", "Moderado"),
        ("severo", "Severo"),
    ]
    granizo_estado = models.CharField(max_length=15, choices=GRANIZO_CHOICES, blank=True, null=True, verbose_name="Granizo")
    granizo_obs    = models.TextField(blank=True, null=True, verbose_name="Detalles del granizo (zonas afectadas)")

    # ── Observaciones técnicas generales ───────────────────
    observaciones_tecnicas = models.TextField(blank=True, null=True, verbose_name="Observaciones técnicas")

    class Meta:
        verbose_name = "Ficha técnica"
        verbose_name_plural = "Fichas técnicas"

    def __str__(self):
        return f"Ficha técnica – {self.vehiculo}"


# ============================================================
# MANTENIMIENTOS DEL VEHÍCULO
# ============================================================
class Mantenimiento(models.Model):
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="mantenimientos",
    )
    nombre = models.CharField(max_length=100, verbose_name="Tipo de mantenimiento")
    fecha = models.DateField(verbose_name="Fecha")
    observacion = models.TextField(blank=True, null=True, verbose_name="Observación")

    class Meta:
        verbose_name = "Mantenimiento"
        verbose_name_plural = "Mantenimientos"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.nombre} – {self.fecha} – {self.vehiculo}"
