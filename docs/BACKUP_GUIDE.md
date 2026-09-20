# Guía de respaldos y recuperación

Los respaldos se guardan bajo `PRIVATE_BACKUP_ROOT`, nunca en `/static/` ni `/media/`. Cada registro incluye responsable, alcance, tamaño y SHA-256.

## Crear respaldo

El usuario indicado debe ser Owner o tener `create_backuprecord`:

```bash
python manage.py create_cw_backup --user NOMBRE_USUARIO --scope database
python manage.py create_cw_backup --user NOMBRE_USUARIO --scope media
python manage.py create_cw_backup --user NOMBRE_USUARIO --scope full
```

Antes de migraciones use al menos `database`; antes de cambios de archivos use `full`. Copie respaldos críticos a almacenamiento externo cifrado y pruebe periódicamente su recuperación en un entorno separado.

## Retención

`DJANGO_BACKUP_RETENTION_DAYS` controla la retención local (30 días por defecto). El comando diario de limpieza es:

```bash
python manage.py cleanup_cw_private_files
```

## Restaurar SQLite

Detenga o recargue fuera de servicio la aplicación antes de restaurar. La orden exige permiso de restauración, confirmación literal, validación del hash y crea otro respaldo inmediatamente antes de reemplazar la base:

```bash
python manage.py restore_cw_backup UUID_DEL_RESPALDO --user NOMBRE_USUARIO --confirm RESTAURAR-CW
```

Después ejecute `python manage.py check`, `python manage.py migrate --plan`, levante la aplicación y pruebe login, dashboard, una solicitud y los logs. La restauración debe ensayarse primero sobre una copia, nunca directamente por intuición.
