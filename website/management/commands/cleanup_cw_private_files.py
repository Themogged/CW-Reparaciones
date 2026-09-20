from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from website.business.exports import resolve_export_path
from website.models import BackupRecord, ExportRecord


class Command(BaseCommand):
    help = "Elimina exportaciones vencidas y respaldos que superan la retención configurada."

    def handle(self, *args, **options):
        now = timezone.now()
        removed_exports = 0
        for export in ExportRecord.objects.filter(expires_at__lte=now).exclude(status=ExportRecord.Status.EXPIRED):
            try:
                resolve_export_path(export).unlink(missing_ok=True)
            except ValueError:
                pass
            export.status = ExportRecord.Status.EXPIRED
            export.relative_path = ""
            export.save(update_fields=("status", "relative_path"))
            removed_exports += 1

        cutoff = now - timedelta(days=settings.WEBSITE_BACKUP_RETENTION_DAYS)
        backup_root = Path(settings.PRIVATE_BACKUP_ROOT).resolve()
        removed_backups = 0
        for backup in BackupRecord.objects.filter(created_at__lt=cutoff, status=BackupRecord.Status.READY):
            candidate = (backup_root / backup.relative_path).resolve()
            if backup.relative_path and backup_root in candidate.parents:
                candidate.unlink(missing_ok=True)
            backup.relative_path = ""
            backup.save(update_fields=("relative_path",))
            removed_backups += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Limpieza completada: {removed_exports} exportaciones y {removed_backups} respaldos."
            )
        )
