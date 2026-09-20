# Informe previo de implementación

Fecha de auditoría: 19 de septiembre de 2026.

## Estado encontrado

- Aplicación Django 6.1.1 monolítica, mantenible y apropiada para PythonAnywhere.
- Sitio público funcional con servicios, cobertura, portafolio autorizado, videos y formulario de solicitudes.
- Administración estándar de Django sin CRM, roles comerciales, dashboard, exportaciones ni centro de respaldos.
- SQLite local con migraciones `0001` a `0009` aplicadas.
- Cero solicitudes y cero clientes en la base local auditada; por lo tanto no se fabricaron datos para KPIs.
- Seguridad previa sólida: CSP con nonce, cookies seguras, controles de host y secreto, rate limiting persistente, adjuntos privados y validación binaria.
- El número de ticket anterior usaba un UUID completo y no era consecutivo.

## Riesgos identificados

1. La administración no separaba responsabilidades de Owner, administración, técnicos, contenido y lectura.
2. No existía ficha de cliente ni asignación de técnico.
3. No había timeline operativo, historial de login ni auditoría de cambios de negocio.
4. Las exportaciones privadas, su caducidad y descarga segura no existían.
5. No había procedimiento integrado y verificable de respaldo/restauración.
6. El panel de PythonAnywhere seguía pendiente de comprobación pública; una validación local no equivale a despliegue.

## Estrategia aplicada

Se preservó el sitio público y su stack. La implementación se agregó por capas dentro de `website`: modelos de negocio, servicios reutilizables, permisos nativos de Django, interfaz administrativa, comandos operativos y pruebas. Antes de migrar se creó una copia local de `db.sqlite3` y se verificó con SHA-256.

## Alcance priorizado

- P0: roles, permisos server-side, integridad de solicitudes, respaldos y exportaciones privadas.
- P1: dashboard, CRM, clientes, WhatsApp, filtros, CSV, Excel, PDF corporativo y administración de contenido existente.
- P2/P3: importador genérico, command palette, analítica avanzada y trabajos asíncronos quedan como evolución explícita, no como funciones simuladas.
