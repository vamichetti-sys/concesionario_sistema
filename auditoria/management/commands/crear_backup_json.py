"""
Backup de datos críticos en JSON.

Uso:
    python manage.py backup_json
    python manage.py backup_json --output /ruta/destino/
    python manage.py backup_json --upload-cloudinary

Genera un archivo concesionario_backup_YYYY-MM-DD_HHMM.json con todos los
registros de los modelos críticos. Para programarlo a diario en Render,
configurar un Cron Job en el dashboard que ejecute este comando.
"""
import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model

# Modelos a respaldar (mismos que MODELOS_AUDITAR + auditoría misma).
MODELOS_BACKUP = [
    ("vehiculos", "Vehiculo"),
    ("vehiculos", "FichaVehicular"),
    ("vehiculos", "FichaTecnica"),
    ("vehiculos", "PagoGastoIngreso"),
    ("vehiculos", "GastoConcesionario"),
    ("vehiculos", "Mantenimiento"),
    ("vehiculos", "ConfiguracionGastosIngreso"),
    ("ventas", "Venta"),
    ("cuentas", "CuentaCorriente"),
    ("cuentas", "PlanPago"),
    ("cuentas", "CuotaPlan"),
    ("cuentas", "Pago"),
    ("cuentas", "PagoCuota"),
    ("cuentas", "MovimientoCuenta"),
    ("cuentas", "BitacoraCuenta"),
    ("clientes", "Cliente"),
    ("clientes", "ReglaComercial"),
    ("crm", "Prospecto"),
    ("crm", "Seguimiento"),
    ("crm", "NotificacionCRM"),
    ("compraventa", "Proveedor"),
    ("compraventa", "CompraVentaOperacion"),
    ("compraventa", "DeudaProveedor"),
    ("compraventa", "PagoProveedor"),
    ("facturacion", "FacturaRegistrada"),
    ("facturacion", "CompraRegistrada"),
    ("boletos", "BoletoCompraventa"),
    ("boletos", "Pagare"),
    ("boletos", "PagareLote"),
    ("boletos", "Reserva"),
    ("boletos", "EntregaDocumentacion"),
    ("reventa", "Reventa"),
    ("reventa", "CuentaRevendedor"),
    ("reventa", "MovimientoRevendedor"),
    ("cheques", "Cheque"),
    ("cuentas_internas", "CuentaInterna"),
    ("cuentas_internas", "MovimientoInterno"),
    ("gestoria", "Gestoria"),
    ("gastos_mensuales", "CategoriaGasto"),
    ("gastos_mensuales", "GastoMensual"),
    ("presupuestos", "Presupuesto"),
    ("inicio", "RecordatorioDashboard"),
    ("asistencia", "Empleado"),
    ("auditoria", "LogActividad"),
]


class Command(BaseCommand):
    help = "Exporta todos los datos críticos a un único archivo JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="",
            help="Directorio destino. Default: directorio actual.",
        )
        parser.add_argument(
            "--upload-cloudinary",
            action="store_true",
            help="Si está seteado, sube el archivo a Cloudinary (requiere CLOUDINARY_URL).",
        )

    def _row_to_dict(self, instance: Model) -> dict:
        data = {}
        for field in instance._meta.fields:
            try:
                val = getattr(instance, field.name, None)
            except Exception:
                val = None
            if val is None:
                data[field.name] = None
            elif field.is_relation:
                data[field.name] = getattr(val, "pk", None)
            else:
                data[field.name] = val
        return data

    def handle(self, *args, **options):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"concesionario_backup_{timestamp}.json"
        output_dir = options["output"] or "."
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        backup = {
            "_meta": {
                "generado": datetime.now().isoformat(),
                "modelos": [],
            }
        }
        total_registros = 0

        for app_label, model_name in MODELOS_BACKUP:
            try:
                Model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stderr.write(self.style.WARNING(
                    f"  ! {app_label}.{model_name} no existe, salteado"
                ))
                continue

            registros = []
            for obj in Model.objects.all().iterator():
                registros.append(self._row_to_dict(obj))

            key = f"{app_label}.{model_name}"
            backup[key] = registros
            backup["_meta"]["modelos"].append({
                "tabla": key,
                "total": len(registros),
            })
            total_registros += len(registros)
            self.stdout.write(f"  OK {key}: {len(registros)} registros")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup, f, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)

        size_kb = os.path.getsize(filepath) / 1024
        self.stdout.write(self.style.SUCCESS(
            f"\nBackup generado: {filepath}\n"
            f"Total: {total_registros} registros, {size_kb:,.0f} KB"
        ))

        if options["upload_cloudinary"]:
            try:
                import cloudinary
                import cloudinary.uploader
                resp = cloudinary.uploader.upload(
                    filepath,
                    resource_type="raw",
                    folder="backups",
                    use_filename=True,
                    unique_filename=False,
                    overwrite=True,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Subido a Cloudinary: {resp.get('secure_url')}"
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"Error subiendo a Cloudinary: {e}"
                ))
