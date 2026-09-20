from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from website.business.backups import create_backup
from website.models import BackupRecord


class Command(BaseCommand):
    help = "Restaura un respaldo SQLite con confirmación literal y respaldo previo automático."

    def add_arguments(self, parser):
        parser.add_argument("backup_id")
        parser.add_argument("--user", required=True)
        parser.add_argument("--confirm", required=True, help="Debe ser RESTAURAR-CW.")

    def handle(self, *args, **options):
        if options["confirm"] != "RESTAURAR-CW":
            raise CommandError("Confirmación inválida. Usa --confirm RESTAURAR-CW.")
        if connection.vendor != "sqlite":
            raise CommandError("La restauración integrada solo admite SQLite.")
        try:
            user = get_user_model().objects.get(username=options["user"], is_active=True)
            backup = BackupRecord.objects.get(
                pk=options["backup_id"],
                scope=BackupRecord.Scope.DATABASE,
                status=BackupRecord.Status.READY,
            )
        except (get_user_model().DoesNotExist, BackupRecord.DoesNotExist) as exc:
            raise CommandError("Usuario o respaldo válido no encontrado.") from exc
        if not (user.is_superuser or user.has_perm("website.restore_backuprecord")):
            raise CommandError("El usuario no tiene permiso para restaurar respaldos.")

        root = Path(settings.PRIVATE_BACKUP_ROOT).resolve()
        source = (root / backup.relative_path).resolve()
        if not backup.relative_path or root not in source.parents or not source.is_file():
            raise CommandError("Ruta de respaldo inválida o archivo ausente.")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != backup.sha256:
            raise CommandError("El hash del respaldo no coincide. Restauración cancelada.")

        safety_copy = create_backup(user=user, scope=BackupRecord.Scope.DATABASE)
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        if settings.BASE_DIR.resolve() not in database_path.parents:
            raise CommandError("La base de datos configurada está fuera del proyecto.")
        connection.close()
        shutil.copy2(source, database_path)
        self.stdout.write(
            self.style.SUCCESS(
                f"Restauración completada. Respaldo de seguridad previo: {safety_copy.pk}."
            )
        )
