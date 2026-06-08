"""
Tests del módulo de cuentas corrientes — el de mayor lógica financiera.
Cubren: cálculo de deuda, aplicación de pagos a cuotas, manejo del
excedente (que no se pierda) y la bitácora de auditoría.
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase

from clientes.models import Cliente
from cuentas.models import (
    CuentaCorriente,
    PlanPago,
    CuotaPlan,
    Pago,
    PagoCuota,
    MovimientoCuenta,
)


class BaseCuentaTest(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre_completo="Cliente Test")
        self.cuenta = CuentaCorriente.objects.create(cliente=self.cliente)

    def _plan_con_dos_cuotas(self, monto_cuota=Decimal("60000")):
        """Crea un plan de 2 cuotas iguales sin interés."""
        plan = PlanPago.objects.create(
            cuenta=self.cuenta,
            descripcion="Plan test",
            cantidad_cuotas=2,
            monto_cuota=monto_cuota,
            fecha_inicio=date(2026, 1, 1),
            monto_financiado=monto_cuota * 2,
        )
        c1 = CuotaPlan.objects.create(
            plan=plan, numero=1, vencimiento=date(2026, 2, 1), monto=monto_cuota
        )
        c2 = CuotaPlan.objects.create(
            plan=plan, numero=2, vencimiento=date(2026, 3, 1), monto=monto_cuota
        )
        return plan, c1, c2

    def _nuevo_pago(self, monto):
        return Pago.objects.create(
            cuenta=self.cuenta, monto_total=monto, forma_pago="efectivo"
        )


class DeudaTests(BaseCuentaTest):
    def test_deuda_inicial_y_real_con_plan(self):
        self._plan_con_dos_cuotas()  # 2 x 60.000 = 120.000
        self.assertEqual(self.cuenta.deuda_total_inicial, Decimal("120000"))
        self.assertEqual(self.cuenta.deuda_total_real, Decimal("120000"))

    def test_gasto_extra_suma_a_la_deuda(self):
        # Un gasto extra (manual debe) debe sumarse a la deuda real
        self._plan_con_dos_cuotas()  # 120.000
        MovimientoCuenta.objects.create(
            cuenta=self.cuenta,
            descripcion="Gasto extra: sellado",
            tipo="debe",
            monto=Decimal("5000"),
            origen="manual",
        )
        self.assertEqual(self.cuenta.deuda_total_real, Decimal("125000"))

    def test_pago_reduce_deuda_real(self):
        _, c1, _ = self._plan_con_dos_cuotas()
        pago = self._nuevo_pago(Decimal("60000"))
        PagoCuota.objects.create(pago=pago, cuota=c1, monto_aplicado=Decimal("60000"))
        c1.marcar_pagada()

        c1.refresh_from_db()
        self.assertEqual(c1.estado, "pagada")
        self.assertEqual(self.cuenta.deuda_total_real, Decimal("60000"))


class CuotaTests(BaseCuentaTest):
    def test_saldo_pendiente_y_marcar_pagada(self):
        _, c1, _ = self._plan_con_dos_cuotas()
        pago = self._nuevo_pago(Decimal("60000"))
        PagoCuota.objects.create(pago=pago, cuota=c1, monto_aplicado=Decimal("60000"))
        c1.marcar_pagada()

        c1.refresh_from_db()
        self.assertEqual(c1.total_pagado, Decimal("60000"))
        self.assertEqual(c1.saldo_pendiente, Decimal("0"))
        self.assertEqual(c1.estado, "pagada")


class AplicarPagoTests(BaseCuentaTest):
    def test_pago_parcial_no_marca_pagada(self):
        _, c1, _ = self._plan_con_dos_cuotas()
        pago = self._nuevo_pago(Decimal("20000"))
        sobra = self.cuenta.aplicar_pago_a_cuotas(pago, Decimal("20000"))

        c1.refresh_from_db()
        self.assertEqual(sobra, Decimal("0"))
        self.assertEqual(c1.saldo_pendiente, Decimal("40000"))
        self.assertEqual(c1.estado, "pendiente")

    def test_pago_se_traslada_a_la_cuota_siguiente(self):
        # Pagar 100.000 sobre 2 cuotas de 60.000: 60.000 a la 1ª, 40.000 a la 2ª
        _, c1, c2 = self._plan_con_dos_cuotas()
        pago = self._nuevo_pago(Decimal("100000"))
        sobra = self.cuenta.aplicar_pago_a_cuotas(pago, Decimal("100000"))

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(sobra, Decimal("0"))
        self.assertEqual(c1.estado, "pagada")
        self.assertEqual(c2.saldo_pendiente, Decimal("20000"))

    def test_excedente_no_se_pierde(self):
        # ISSUE 14: pagar 150.000 sobre 120.000 → 30.000 de excedente devuelto
        _, c1, c2 = self._plan_con_dos_cuotas()
        pago = self._nuevo_pago(Decimal("150000"))
        sobra = self.cuenta.aplicar_pago_a_cuotas(pago, Decimal("150000"))

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.estado, "pagada")
        self.assertEqual(c2.estado, "pagada")
        self.assertEqual(sobra, Decimal("30000"))

    def test_cuota_preferida_recibe_primero(self):
        # Pago de 100.000 con preferencia por la 2ª cuota:
        # 60.000 a la 2ª (queda paga) y 40.000 a la 1ª.
        _, c1, c2 = self._plan_con_dos_cuotas()
        pago = self._nuevo_pago(Decimal("100000"))
        sobra = self.cuenta.aplicar_pago_a_cuotas(
            pago, Decimal("100000"), cuota_preferida=c2
        )

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(sobra, Decimal("0"))
        self.assertEqual(c2.estado, "pagada")
        self.assertEqual(c1.saldo_pendiente, Decimal("20000"))


class BitacoraTests(BaseCuentaTest):
    def test_log_escribe_bitacora(self):
        # ISSUE 15: el helper log() registra en la bitácora
        self.assertEqual(self.cuenta.bitacora.count(), 0)
        self.cuenta.log("Pago registrado", "Recibo RC-2026-000001")
        self.assertEqual(self.cuenta.bitacora.count(), 1)
        entrada = self.cuenta.bitacora.first()
        self.assertEqual(entrada.accion, "Pago registrado")

    def test_log_nunca_rompe(self):
        # Aunque el detalle sea None, no debe lanzar excepción
        try:
            self.cuenta.log("Accion", None)
        except Exception as exc:  # pragma: no cover
            self.fail(f"log() no debería romper: {exc}")
        self.assertEqual(self.cuenta.bitacora.count(), 1)
