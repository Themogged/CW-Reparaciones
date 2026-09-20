# Despliegue seguro en PythonAnywhere

Esta guía no sustituye una verificación real en el panel. No recargue a ciegas.

## 1. Respaldo y actualización

En una consola Bash de PythonAnywhere:

```bash
cd /home/CWreparaciones/CW-Reparaciones
cp db.sqlite3 "$HOME/db-before-business-control-$(date +%Y%m%d-%H%M%S).sqlite3"
git status --short
git pull --ff-only origin main
source /home/CWreparaciones/.virtualenvs/cw-reparaciones/bin/activate
python -m pip install -r requirements.txt
```

Adapte la ruta únicamente si la pestaña **Web** muestra otra ruta real.

## 2. Validar antes de migrar

```bash
python manage.py check
python manage.py migrate --plan
```

Revise que aparezcan `0010_business_control_center`, `0011_login_history` y
`0012_backfill_crm_and_sequences`. Luego:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

## 3. Configuración Web

- Código fuente: directorio que contiene `manage.py`.
- Working directory: el mismo repositorio.
- Virtualenv: `/home/CWreparaciones/.virtualenvs/cw-reparaciones`.
- `/static/` apunta al `STATIC_ROOT` absoluto.
- `/media/` apunta a `MEDIA_ROOT` sólo para contenido público autorizado.
- No cree mapeos para `private_uploads`, `private_exports` ni `private_backups`.

Mantenga `DJANGO_DEBUG=false`, un secreto aleatorio, hosts/orígenes exactos, `DJANGO_TRUST_X_REAL_IP=true` en PythonAnywhere y HTTPS validado. Las carpetas privadas deben ser persistentes y legibles sólo por la cuenta.

## 4. Recarga y smoke test

Pulse **Reload** y revise primero los logs de error. Después compruebe en el dominio real:

1. Inicio público en móvil y escritorio.
2. Login y logout administrativo.
3. Dashboard sin errores y sin KPIs inventados.
4. Creación controlada de una solicitud de prueba autorizada.
5. Asignación, cambio de estado y orden PDF.
6. Exportación CSV, Excel y PDF; descarga con una cuenta autorizada y rechazo con otra.
7. Adjunto privado y restricción del técnico a casos asignados.
8. `python manage.py check --deploy` con las variables reales.

Si algo falla, no repita migraciones al azar: consulte `cwreparaciones.pythonanywhere.com.error.log`, confirme ruta/virtualenv y restaure sólo con el procedimiento documentado.
