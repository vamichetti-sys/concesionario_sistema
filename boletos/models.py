from django.db import models, transaction
from decimal import Decimal
from django.utils.timezone import now

from clientes.models import Cliente
from vehiculos.models import Vehiculo
from ventas.models import Venta
from cuentas.models import CuentaCorriente


# ==========================================================
# BOLETO DE COMPRAVENTA (EXISTENTE – NO TOCAR)
# ==========================================================
class BoletoCompraventa(models.Model):

    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="boletos"
    )

    cuenta_corriente = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="boletos"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="boletos"
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        related_name="boletos",
        null=True,
        blank=True
    )

    numero = models.PositiveIntegerField()
    texto_final = models.TextField()

    pdf = models.FileField(
        upload_to="boletos/",
        null=True,
        blank=True
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Boleto #{self.numero} - {self.cliente}"


# ==========================================================
# LOTE DE PAGARÉS
# ==========================================================
class PagareLote(models.Model):

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pagares_lotes"
    )

    beneficiario = models.CharField(
        max_length=255,
        default="AMICHETTI HUGO ALBERTO"
    )

    lugar_emision = models.CharField(
        max_length=100,
        default="Rojas"
    )

    fecha_emision = models.DateField(default=now)

    monto_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00")
    )

    cantidad = models.PositiveIntegerField(default=1)

    dia_vencimiento = models.PositiveIntegerField(
        default=10,
        verbose_name="Día de vencimiento mensual"
    )

    pdf = models.FileField(
        upload_to="pagares/lotes/",
        null=True,
        blank=True
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Lote de pagarés ({self.cantidad}) - {self.cliente}"


# ==========================================================
# PAGARÉ (INDIVIDUAL – LEGAL)
# ==========================================================
class Pagare(models.Model):

    lote = models.ForeignKey(
        PagareLote,
        on_delete=models.CASCADE,
        related_name="pagares",
        null=True,
        blank=True
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pagares"
    )

    numero = models.PositiveIntegerField(unique=True)

    beneficiario = models.CharField(
        max_length=255,
        default="AMICHETTI HUGO ALBERTO"
    )

    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00")
    )

    lugar_emision = models.CharField(
        max_length=100,
        default="Rojas"
    )

    fecha_emision = models.DateField(default=now)

    fecha_vencimiento = models.DateField(
        null=True,
        blank=True
    )

    pdf = models.FileField(
        upload_to="pagares/",
        null=True,
        blank=True
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Pagaré #{self.numero} - {self.cliente} - ${self.monto}"


# ==========================================================
# RESERVA DE VEHÍCULO
# ==========================================================
class Reserva(models.Model):

    # ── Datos del Solicitante ──────────────────────────────
    apellido_nombre = models.CharField("Apellido y Nombre / Razón Social", max_length=200)
    dni             = models.CharField("DNI", max_length=20)
    domicilio       = models.CharField("Domicilio", max_length=300)
    telefono        = models.CharField("Teléfono", max_length=50)
    cuit            = models.CharField("CUIT", max_length=20, blank=True)
    iva             = models.CharField("I.V.A.", max_length=50, blank=True)

    # ── Datos del Vehículo ────────────────────────────────
    marca      = models.CharField("Marca", max_length=100)
    modelo     = models.CharField("Modelo", max_length=100)
    anio       = models.CharField("Año", max_length=10, blank=True)
    dominio    = models.CharField("Dominio", max_length=20, blank=True)
    motor_nro  = models.CharField("Motor N°", max_length=100, blank=True)
    chasis_nro = models.CharField("Chasis N°", max_length=100, blank=True)

    # Vínculo opcional con el stock
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas"
    )

    # ── Detalle de la Operación ───────────────────────────
    precio_vehiculo = models.DecimalField("Precio del Vehículo", max_digits=15, decimal_places=2, null=True, blank=True)
    opcionales      = models.DecimalField("Opcionales / Otros gastos", max_digits=15, decimal_places=2, null=True, blank=True)
    total_a_pagar   = models.DecimalField("Total a Pagar", max_digits=15, decimal_places=2, null=True, blank=True)
    senia           = models.DecimalField("Seña", max_digits=15, decimal_places=2, null=True, blank=True)

    # ── Propuesta de Pago ─────────────────────────────────
    contado_efectivo  = models.DecimalField("Contado Efectivo", max_digits=15, decimal_places=2, null=True, blank=True)
    pago_entrega      = models.DecimalField("A pagar contra entrega (efectivo)", max_digits=15, decimal_places=2, null=True, blank=True)
    cheques           = models.TextField("Cheques (detalle)", blank=True)
    total_propuesta   = models.DecimalField("Total Propuesta", max_digits=15, decimal_places=2, null=True, blank=True)
    credito_prendario = models.BooleanField("Crédito Prendario autorizado", default=False)
    otro_concepto     = models.CharField("Otro concepto", max_length=300, blank=True)
    cant_cuotas       = models.IntegerField("Cantidad de Cuotas", null=True, blank=True)
    valor_cuota       = models.DecimalField("Valor de Cuota", max_digits=15, decimal_places=2, null=True, blank=True)
    dia_cuota         = models.CharField("Día de Vencimiento Cuota", max_length=10, blank=True)

    # ── Vehículo Usado en Parte de Pago (Permuta) ─────────
    permuta_marca   = models.CharField("Marca (usado)", max_length=100, blank=True)
    permuta_patente = models.CharField("Patente (usado)", max_length=20, blank=True)
    permuta_suma    = models.DecimalField("Suma propuesta (usado)", max_digits=15, decimal_places=2, null=True, blank=True)
    permuta_total   = models.DecimalField("Total con permuta", max_digits=15, decimal_places=2, null=True, blank=True)

    # ── Observaciones ─────────────────────────────────────
    observaciones = models.TextField("Observaciones", blank=True)

    # ── Metadatos ─────────────────────────────────────────
    numero_reserva = models.CharField("N° Reserva", max_length=20, unique=True, blank=True)
    fecha_reserva  = models.DateField("Fecha de Reserva", default=now)
    creado         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"

    def __str__(self):
        return f"Reserva #{self.numero_reserva} – {self.apellido_nombre} – {self.marca} {self.modelo}"

    def save(self, *args, **kwargs):
        if not self.numero_reserva:
            with transaction.atomic():
                ultimo = Reserva.objects.select_for_update().aggregate(mx=models.Max("id"))["mx"] or 0
                self.numero_reserva = f"RES-{(ultimo + 1):04d}"
                super().save(*args, **kwargs)
                return
        super().save(*args, **kwargs)


# ============================================================
# ENTREGA DE DOCUMENTACION
# ============================================================
class EntregaDocumentacion(models.Model):

    SI_NO = [
        ("si", "Si"),
        ("no", "No"),
    ]

    # Datos del vehiculo (auto-completables desde Vehiculo)
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entregas_documentacion",
    )
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    dominio = models.CharField(max_length=20)
    anio = models.CharField(max_length=10, blank=True, null=True)
    motor = models.CharField(max_length=100, blank=True, null=True)
    chasis = models.CharField(max_length=100, blank=True, null=True)

    # Datos del comprador
    nombre_comprador = models.CharField(max_length=150)
    dni_comprador = models.CharField(max_length=20, blank=True, null=True)
    domicilio_comprador = models.CharField(max_length=200, blank=True, null=True)
    telefono_comprador = models.CharField(max_length=50, blank=True, null=True)

    # Checklist de documentacion entregada
    titulo = models.CharField(max_length=2, choices=SI_NO, default="no")
    cedula = models.CharField(max_length=2, choices=SI_NO, default="no")
    cedula_azul = models.CharField(max_length=2, choices=SI_NO, default="no")
    formulario_08 = models.CharField(max_length=2, choices=SI_NO, default="no")
    formulario_02 = models.CharField(max_length=2, choices=SI_NO, default="no")
    formulario_12 = models.CharField(max_length=2, choices=SI_NO, default="no")
    formulario_13d = models.CharField(max_length=2, choices=SI_NO, default="no")
    gp01 = models.CharField(max_length=2, choices=SI_NO, default="no", verbose_name="GP 01")
    gnc = models.CharField(max_length=2, choices=SI_NO, default="no", verbose_name="GNC")
    vtv = models.CharField(max_length=2, choices=SI_NO, default="no", verbose_name="VTV")
    verificacion_policial = models.CharField(max_length=2, choices=SI_NO, default="no")
    informe_dominio = models.CharField(max_length=2, choices=SI_NO, default="no")
    infracciones = models.CharField(max_length=2, choices=SI_NO, default="no")
    patentes_al_dia = models.CharField(max_length=2, choices=SI_NO, default="no")
    libre_deuda = models.CharField(max_length=2, choices=SI_NO, default="no")
    manuales = models.CharField(max_length=2, choices=SI_NO, default="no")
    codigo_radio = models.CharField(max_length=2, choices=SI_NO, default="no")
    llave_duplicado = models.CharField(max_length=2, choices=SI_NO, default="no")
    rueda_auxilio = models.CharField(max_length=2, choices=SI_NO, default="no")
    gato_llave_rueda = models.CharField(max_length=2, choices=SI_NO, default="no")

    # Observaciones
    observaciones = models.TextField(blank=True, null=True)

    # Fecha y metadatos
    fecha = models.DateField(default=now)
    hora = models.TimeField(blank=True, null=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Entrega de documentacion"
        verbose_name_plural = "Entregas de documentacion"

    def __str__(self):
        return f"Entrega – {self.nombre_comprador} – {self.marca} {self.modelo} ({self.dominio})"

    def items_entregados(self):
        """Retorna lista de items marcados como SI."""
        campos = [
            ("Titulo", self.titulo),
            ("Cedula", self.cedula),
            ("Cedula azul", self.cedula_azul),
            ("Formulario 08", self.formulario_08),
            ("Formulario 02", self.formulario_02),
            ("Formulario 12", self.formulario_12),
            ("Formulario 13D", self.formulario_13d),
            ("GP 01", self.gp01),
            ("GNC", self.gnc),
            ("VTV", self.vtv),
            ("Verificacion policial", self.verificacion_policial),
            ("Informe de dominio", self.informe_dominio),
            ("Infracciones", self.infracciones),
            ("Patentes al dia", self.patentes_al_dia),
            ("Libre deuda", self.libre_deuda),
            ("Manuales", self.manuales),
            ("Codigo radio", self.codigo_radio),
            ("Llave duplicado", self.llave_duplicado),
            ("Rueda de auxilio", self.rueda_auxilio),
            ("Gato / llave de rueda", self.gato_llave_rueda),
        ]
        return [(nombre, valor) for nombre, valor in campos]
