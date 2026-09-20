from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from website.business.backups import create_backup
from website.models import BackupRecord


class Command(BaseCommand):
    help = "Crea un respaldo privado, registra su hash y deja trazabilidad."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="Usuario responsable del respaldo.")
        parser.add_argument(
            "--scope",
            choices=BackupRecord.Scope.values,
            default=BackupRecord.Scope.DATABASE,
            help="database, media o full.",
        )

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options["user"], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("El usuario responsable no existe o está inactivo.") from exc
        if not (user.is_superuser or user.has_perm("website.create_backuprecord")):
            raise CommandError("El usuario no tiene permiso para crear respaldos.")
        record = create_backup(user=user, scope=options["scope"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Respaldo {record.pk} creado: {record.relative_path} · SHA-256 {record.sha256}"
            )
        )
