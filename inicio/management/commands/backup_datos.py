"""
Backup de datos (red de seguridad, además del backup automático de Render).

Uso:
    python manage.py backup_datos

Genera un JSON restaurable en la carpeta backups/ (ignorada por git).
Se restaura con:  python manage.py loaddata backups/<archivo>.json
"""
from datetime import datetime
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Exporta un backup de los datos a un JSON (red de seguridad)."

    EXCLUIR = [
        "contenttypes",
        "auth.permission",
        "sessions.session",
        "admin.logentry",
    ]

    def handle(self, *args, **options):
        carpeta = Path("backups")
        carpeta.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta / f"backup_{ts}.json"

        with open(destino, "w", encoding="utf-8") as f:
            call_command(
                "dumpdata",
                *[f"--exclude={e}" for e in self.EXCLUIR],
                indent=2,
                stdout=f,
            )

        size_kb = destino.stat().st_size / 1024
        self.stdout.write(self.style.SUCCESS(
            f"Backup guardado en {destino} ({size_kb:,.0f} KB). "
            f"Restaurar con: python manage.py loaddata {destino}"
        ))
