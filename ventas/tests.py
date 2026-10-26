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


from django.test import override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class ComisionesPdfTests(TestCase):
    def setUp(self):
        admin = User.objects.create_user(
            "admin_test", password="x", is_superuser=True, is_staff=True)
        self.client.force_login(admin)
        self.vendedor = User.objects.create_user("juan", first_name="Juan")
        cuenta = CuentaVendedor.objects.create(vendedor=self.vendedor)
        MovimientoComision.objects.create(
            cuenta=cuenta, tipo="comision", monto=Decimal("50000"), descripcion="venta Focus")
        MovimientoComision.objects.create(
            cuenta=cuenta, tipo="pago", monto=Decimal("20000"))

    def test_resumen_general_pdf(self):
        r = self.client.get(reverse("ventas:comisiones_resumen_pdf"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_resumen_vendedor_pdf(self):
        r = self.client.get(reverse("ventas:comision_vendedor_pdf", args=[self.vendedor.id]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_boton_imprimir_en_pantallas(self):
        r = self.client.get(reverse("ventas:comisiones_vendedores"))
        self.assertContains(r, reverse("ventas:comisiones_resumen_pdf"))
        r = self.client.get(reverse("ventas:detalle_comision_vendedor", args=[self.vendedor.id]))
        self.assertContains(r, reverse("ventas:comision_vendedor_pdf", args=[self.vendedor.id]))
