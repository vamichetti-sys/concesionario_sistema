from django.db import models
from decimal import Decimal
from django.apps import apps


# ============================================================
# VEHICULO
# ============================================================
class Vehiculo(models.Model):
    ESTADOS = [
        ('stock', 'En stock'),
        ('temporal', 'Temporalmente no disponible'),
        ('vendido', 'Vendido'),
    ]

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    dominio = models.CharField(max_length=10, unique=True)

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

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.dominio})"

    @property
    def tiene_venta(self):
        return hasattr(self, "venta")

    @property
    def esta_vendido_correctamente(self):
        return self.estado == "vendido" and self.tiene_venta

    def puede_eliminarse(self):
        return not self.tiene_venta


# ============================================================
# FICHA VEHICULAR COMPLETA
# ============================================================
class FichaVehicular(models.Model):

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="ficha"
    )

    numero_motor = models.CharField(max_length=100, blank=True, null=True)
    numero_chasis = models.CharField(max_length=100, blank=True, null=True)

    fecha_inscripcion_inicial = models.DateField(blank=True, null=True)

    motor = models.CharField(max_length=100, blank=True, null=True)
    chasis = models.CharField(max_length=100, blank=True, null=True)

    color = models.CharField(max_length=50, blank=True, null=True)
    combustible = models.CharField(max_length=50, blank=True, null=True)
    transmision = models.CharField(max_length=50, blank=True, null=True)

    vendedor = models.CharField(max_length=200, blank=True, null=True)
    contacto = models.CharField(max_length=200, blank=True, null=True)
    email_contacto = models.CharField(max_length=200, blank=True, null=True)

    titular = models.CharField(max_length=200, blank=True, null=True)
    domicilio_titular = models.CharField(max_length=200, blank=True, null=True)
    dni_titular = models.CharField(max_length=20, blank=True, null=True)
    estado_civil = models.CharField(max_length=50, blank=True, null=True)
    cuit_cuil_dni = models.CharField(max_length=50, blank=True, null=True)

    tipo_ingreso = models.CharField(
        max_length=50,
        choices=[
            ("compra", "Compra"),
            ("consignacion", "Consignación"),
        ],
        blank=True,
        null=True
    )

    numero_consignacion_factura = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    ESTADO_DOC = [
        ("tiene", "Tiene"),
        ("no_tiene", "No tiene"),
    ]

    patentes_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    patentes_monto = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    patentes_vto1 = models.DateField(blank=True, null=True)
    patentes_vto2 = models.DateField(blank=True, null=True)
    patentes_vto3 = models.DateField(blank=True, null=True)
    patentes_vto4 = models.DateField(blank=True, null=True)
    patentes_vto5 = models.DateField(blank=True, null=True)

    f08_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    cedula_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)

    verificacion_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    verificacion_vencimiento = models.DateField(blank=True, null=True)

    autopartes_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    autopartes_turno = models.DateField(blank=True, null=True)
    autopartes_turno_obs = models.CharField(max_length=200, blank=True, null=True)

    vtv_estado = models.CharField(max_length=20, choices=ESTADO_DOC, blank=True, null=True)
    vtv_turno = models.DateField(blank=True, null=True)
    vtv_vencimiento = models.DateField(blank=True, null=True)

    gasto_f08 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_informes = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_patentes = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_verificacion = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_autopartes = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_vtv = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_r541 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    gasto_firmas = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    total_gastos = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

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
            "Verificación": self.gasto_verificacion,
            "Autopartes": self.gasto_autopartes,
            "VTV": self.gasto_vtv,
            "R541": self.gasto_r541,
            "Firmas": self.gasto_firmas,
        }

    def total_pagado_por_concepto(self, concepto):
        PagoGasto = apps.get_model("vehiculos", "PagoGastoIngreso")
        total = (
            PagoGasto.objects.filter(
                vehiculo=self.vehiculo,
                concepto=concepto
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

    class Meta:
        ordering = ["fecha_pago"]

    def __str__(self):
        return f"{self.vehiculo} - {self.concepto} - ${self.monto}"
