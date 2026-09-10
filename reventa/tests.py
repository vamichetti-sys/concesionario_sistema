"""Tests del plan de pagos por auto en la cuenta del revendedor.
Al pagar una cuota se registra un 'haber' y baja el saldo; deshacer lo revierte."""
from decimal import Decimal
from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User

from reventa.models import (
    CuentaRevendedor, MovimientoRevendedor, PlanReventa, CuotaReventa,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class PlanReventaTests(TestCase):
    def setUp(self):
        # Superuser: el middleware de permisos lo deja pasar.
        self.user = User.objects.create_user(
            "rev_admin", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_login(self.user)
        self.cuenta = CuentaRevendedor.objects.create(nombre="Agencia Test")
        MovimientoRevendedor.objects.create(
            cuenta=self.cuenta, tipo="debe", monto=Decimal("900000"),
            descripcion="Reventa auto",
        )
        self.cuenta.refresh_from_db()

    def _plan_con_cuota(self, monto=Decimal("300000")):
        plan = PlanReventa.objects.create(
            cuenta=self.cuenta, descripcion="plan", fecha_inicio=date(2026, 1, 1),
        )
        cuota = CuotaReventa.objects.create(
            plan=plan, numero=1, vencimiento=date(2026, 1, 1), monto=monto,
        )
        return plan, cuota

    def test_saldo_inicial(self):
        self.assertEqual(self.cuenta.saldo, Decimal("900000"))

    def test_propiedades_total_pagado_saldo(self):
        plan, _ = self._plan_con_cuota()
        CuotaReventa.objects.create(plan=plan, numero=2, vencimiento=date(2026, 2, 1), monto=Decimal("300000"))
        self.assertEqual(plan.total, Decimal("600000"))
        self.assertEqual(plan.pagado, Decimal("0"))
        self.assertEqual(plan.saldo, Decimal("600000"))

    def test_pagar_cuota_registra_haber_y_baja_saldo(self):
        _, cuota = self._plan_con_cuota()
        self.client.post(reverse("reventa:pagar_cuota", args=[cuota.id]))
        cuota.refresh_from_db()
        self.cuenta.refresh_from_db()
        self.assertTrue(cuota.pagada)
        self.assertIsNotNone(cuota.movimiento_id)
        # 900.000 - 300.000 = 600.000
        self.assertEqual(self.cuenta.saldo, Decimal("600000"))

    def test_deshacer_cuota_restaura_saldo(self):
        _, cuota = self._plan_con_cuota()
        self.client.post(reverse("reventa:pagar_cuota", args=[cuota.id]))
        self.client.post(reverse("reventa:deshacer_cuota", args=[cuota.id]))
        cuota.refresh_from_db()
        self.cuenta.refresh_from_db()
        self.assertFalse(cuota.pagada)
        self.assertEqual(self.cuenta.saldo, Decimal("900000"))
