# Guía de exportaciones CW

## Formatos

Desde **Solicitudes de servicio**, seleccione los registros y elija CSV, Excel, PDF corporativo o JSON.

- **CSV:** UTF-8 con BOM; neutraliza valores que comienzan por `=`, `+`, `-` o `@` para evitar ejecución de fórmulas.
- **Excel:** hojas Resumen y Solicitudes, encabezado CW, filtros, panel congelado, fechas reales, anchos y filas alternadas; no contiene macros.
- **PDF:** A4 horizontal para el reporte, logo SVG oficial sin deformación, identidad CW, KPIs reales, encabezado, pie y página X de Y.
- **JSON:** UTF-8, portable y sin campos internos ajenos al dataset de solicitudes.

## Seguridad

Cada archivo se guarda fuera de `MEDIA_ROOT`, recibe SHA-256 y caduca según `DJANGO_EXPORT_RETENTION_HOURS` (24 horas por defecto). La descarga vuelve a comprobar autenticación, permiso, propietario o rol autorizado, vigencia, ruta y hash. La URL no es pública ni permanente.

El historial aparece en **Historial de exportaciones**. Para limpiar archivos vencidos:

```bash
python manage.py cleanup_cw_private_files
```

En producción programe este comando diariamente con una tarea de PythonAnywhere.

## Orden de servicio

En la ficha de una solicitud existen dos vistas:

- **Orden cliente:** excluye notas internas, UTM, auditoría e identificadores técnicos.
- **Orden interna:** agrega notas operativas y muestra la marca `USO INTERNO`.
