# Guía del Centro de Control CW

## Acceso y roles

El administrador usa la ruta definida en `DJANGO_ADMIN_URL`. Los permisos se aplican en servidor; ocultar un botón nunca es el único control.

- **Owner:** acceso total, usuarios, permisos, auditoría, exportaciones y respaldos.
- **Administrador:** operación diaria y usuarios, sin restauración de base de datos.
- **Técnico:** únicamente solicitudes asignadas, adjuntos y notas necesarias.
- **Gestor de contenido:** servicios, cobertura, marcas, portafolio, videos, FAQ y reseñas.
- **Solo lectura:** visualización autorizada, sin edición ni exportación privada.

Una cuenta nueva no recibe automáticamente acceso a datos privados. Un Owner debe abrir **Perfiles de usuarios**, seleccionar el rol y guardar. Nunca desactive ni cambie el rol del último Owner activo: el sistema lo bloquea.

## Flujo diario recomendado

1. Abra **Resumen del negocio** y revise solicitudes nuevas o sin técnico.
2. Entre a **Solicitudes de servicio** y use búsqueda por ticket, cliente, teléfono, equipo, marca, zona o problema.
3. Asigne un técnico, cambie el estado y programe la visita si ya fue confirmada.
4. Registre información técnica en notas técnicas y comentarios puntuales en el timeline.
5. Use **Abrir conversación** para iniciar WhatsApp con ticket y nombre ya incluidos.
6. Genere una **Orden cliente** o **Orden interna** según el destinatario.
7. Finalice la solicitud sólo cuando el servicio esté cerrado; la fecha de finalización se registra automáticamente.

## Solicitudes recibidas fuera de la web

Cuando un cliente llama, escribe por WhatsApp o solicita el servicio de forma
presencial, abra **Solicitudes de servicio** y pulse **Nueva solicitud manual**.

1. Seleccione cómo llegó la solicitud.
2. Registre el equipo, el problema y los datos de contacto confirmados.
3. Marque la autorización de datos únicamente después de recibirla del cliente.
4. Asigne un técnico o programe la visita si ya están confirmados.
5. Guarde. El sistema creará el número CW, la ficha del cliente, la auditoría y
   el timeline, y abrirá la solicitud recién creada.
6. Desde esa pantalla puede generar la **Orden cliente** o la **Orden interna**.

No es necesario completar el formulario público en nombre del cliente. El origen
manual queda registrado para distinguirlo de las solicitudes enviadas por la web.

## Clientes y duplicados

Cada solicitud se vincula a una ficha CRM. Teléfono, WhatsApp y correo se normalizan para reutilizar coincidencias exactas. Coincidencias ambiguas se marcan para revisión; el sistema no fusiona perfiles dudosos automáticamente.

## Papelera y concurrencia

Las solicitudes se envían a papelera en vez de borrarse físicamente. Sólo usuarios con el permiso de restauración pueden recuperarlas. Si dos personas editan la misma solicitud, la segunda recibe un aviso y debe recargar antes de guardar para no pisar cambios.

## Datos que no deben inventarse

No publique una reseña sin verificación y origen real. No marque una marca como autorizada sin soporte documental. No agregue precios, garantías, ingresos ni diagnósticos que no estén confirmados.
