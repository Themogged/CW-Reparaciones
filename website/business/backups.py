from __future__ import annotations

import hashlib
import sqlite3
import zipfile
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from website.models import AuditEvent, BackupRecord


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(*, user, scope: str = BackupRecord.Scope.DATABASE) -> BackupRecord:
    if scope not in BackupRecord.Scope.values:
        raise ValueError("Alcance de respaldo no permitido.")
    record = BackupRecord.objects.create(created_by=user, scope=scope)
    root = Path(settings.PRIVATE_BACKUP_ROOT).resolve()
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    extension = ".sqlite3" if scope == BackupRecord.Scope.DATABASE else ".zip"
    relative = Path(timezone.localdate().isoformat()) / f"cw-backup-{scope}-{stamp}-{record.pk}{extension}"
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError("Ruta de respaldo no segura.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        if scope == BackupRecord.Scope.DATABASE:
            connection.ensure_connection()
            if connection.vendor != "sqlite":
                raise RuntimeError("Este respaldo integrado está limitado a SQLite.")
            destination = sqlite3.connect(temporary)
            try:
                connection.connection.backup(destination)
            finally:
                destination.close()
        else:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                if scope == BackupRecord.Scope.FULL:
                    connection.ensure_connection()
                    database_copy = target.parent / f"{record.pk}-database.sqlite3.tmp"
                    destination = sqlite3.connect(database_copy)
                    try:
                        connection.connection.backup(destination)
                    finally:
                        destination.close()
                    archive.write(database_copy, "database/db.sqlite3")
                    database_copy.unlink(missing_ok=True)
                media_root = Path(settings.MEDIA_ROOT)
                if media_root.exists():
                    for path in media_root.rglob("*"):
                        if path.is_file():
                            archive.write(path, Path("media") / path.relative_to(media_root))
        temporary.replace(target)
        record.status = BackupRecord.Status.READY
        record.relative_path = relative.as_posix()
        record.size_bytes = target.stat().st_size
        record.sha256 = _sha256(target)
        record.save(update_fields=("status", "relative_path", "size_bytes", "sha256"))
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.BACKUP,
            object_type="website.backuprecord",
            object_id=str(record.pk),
            object_repr=relative.name,
            changes={"scope": scope, "size_bytes": record.size_bytes},
        )
        return record
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        record.status = BackupRecord.Status.FAILED
        record.error_message = str(exc)[:500]
        record.save(update_fields=("status", "error_message"))
        raise
