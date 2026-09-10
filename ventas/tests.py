"""Tests de comisiones de vendedores: el saldo = comisiones - pagos."""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User

from ventas.models import CuentaVendedor, MovimientoComision


class ComisionTests(TestCase):
    def _cuenta(self, username):
        u = User.objects.create_user(username, password="x")
        return CuentaVendedor.objects.create(vendedor=u)

    def test_saldo_comisiones_menos_pagos(self):
        cta = self._cuenta("vend1")
        MovimientoComision.objects.create(cuenta=cta, tipo="comision", monto=Decimal("100000"))
        MovimientoComision.objects.create(cuenta=cta, tipo="comision", monto=Decimal("50000"))
        MovimientoComision.objects.create(cuenta=cta, tipo="pago", monto=Decimal("30000"))
        cta.refresh_from_db()
        # 150.000 de comisiones - 30.000 pagado = 120.000
        self.assertEqual(cta.saldo, Decimal("120000"))

    def test_borrar_movimiento_recalcula_saldo(self):
        cta = self._cuenta("vend2")
        m = MovimientoComision.objects.create(cuenta=cta, tipo="comision", monto=Decimal("80000"))
        cta.refresh_from_db()
        self.assertEqual(cta.saldo, Decimal("80000"))
        m.delete()
        cta.refresh_from_db()
        self.assertEqual(cta.saldo, Decimal("0"))
