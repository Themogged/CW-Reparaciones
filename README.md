# CW Reparaciones

Plataforma Django de CW Reparaciones con catálogo de ocho equipos, cobertura
consultable, WhatsApp, solicitudes guiadas, administración y videos de trabajos
autorizados. La V1 local no equivale a un despliegue público: los datos legales,
dominio y hosting pendientes figuran en [BUSINESS_DATA_PENDING.md](BUSINESS_DATA_PENDING.md).

## Puesta en marcha local

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

La web queda disponible en `http://127.0.0.1:8000/` y la administración en
`http://127.0.0.1:8000/admin/`.

## Configuración comercial

Los datos editables se gestionan desde el administrador:

- identidad, canales de contacto, redes y horarios;
- visibilidad de módulos;
- categorías y servicios;
- preguntas frecuentes;
- proyectos, videos y reseñas con control de autorización;
- solicitudes recibidas.

El brief aportó el teléfono/WhatsApp `+57 317 504 0053`, correo
`charlesrodriguez2009@hotmail.com`, perfil `@cwreparaciones`, país Colombia y
zona horaria `America/Bogota`. No se muestra dirección física, horario, marcas,
tarifas, reseñas o garantía sin confirmación concreta. La cobertura menciona
Bello, Itagüí, El Poblado, Sabaneta y La Estrella; la disponibilidad para una
dirección específica se consulta antes de prometer atención.

El catálogo incluye lavadoras, neveras, estufas de inducción, lavavajillas,
aires acondicionados, abanicos/ventiladores, hornos industriales y lavadoras
industriales. Cada servicio tiene URL y contenido editable en el admin. Las
marcas de referencia están guardadas sin declarar soporte ni autorización oficial.

## Solicitudes y archivos

El formulario se describe como recopilación preliminar, no como diagnóstico ni
cita confirmada. Incluye equipo, marca/modelo opcionales, problema, municipio,
sector, contacto, fecha preferida opcional, consentimiento, honeypot, limitación
básica por IP y captura UTM. Genera un número `CW-AAAA-UUID`, estable y único,
visible al finalizar. Los adjuntos JPEG, PNG, WebP y MP4 se validan por
extensión, firma binaria y tamaño. Se guardan bajo `private_uploads/`, sin ruta
pública; la descarga requiere personal con permiso específico.

Las solicitudes se guardan en el admin. La notificación interna por correo está
deshabilitada hasta configurar remitente, destinatario y SMTP reales; cargar el
correo público no basta para activar avisos. Mientras tanto el equipo debe
revisar el panel.

## Videos y trabajos reales

Dos clips propios y autorizados por el usuario se registran como casos: revisión
interna de una lavadora y trabajo técnico en una máquina de cafetería. Un tercer
video autorizado se publica como presentación de CW Reparaciones, sin atribuirle
la condición de trabajo real. Los tres originales 4K se conservan privados. El
visitante recibe solo versiones H.264 optimizadas: previews mudos de 540×960
(12 segundos en los casos y 7 en la presentación) y videos completos de 720×1280
para reproducción manual, cada uno con póster. No se atribuyen marcas,
diagnósticos o resultados ausentes del material.

En móvil, el primer preview autorizado aparece dentro del hero junto a los
canales de contacto. Solo el video suficientemente visible se reproduce sin
sonido; al desplazarse se pausa, y los demás clips no se descargan al abrir
la página. La presentación de marca tiene un preview independiente en Inicio y
el video completo con controles en Nosotros; no se mezcla con las fichas de
trabajos reales. La ficha de cada caso permite reproducir su video completo
manualmente. Cada video publicado y autorizado incluye metadatos `VideoObject`
con URL pública del póster y del video optimizado; nunca referencia el original
privado. Su fecha de carga corresponde al registro del video en el sitio.

La importación local de la presentación exige el original esperado, derivados
válidos y una confirmación explícita de autorización. El comando es idempotente:

```powershell
.\.venv\Scripts\python.exe manage.py import_authorized_cw_brand_video --original 'C:\ruta\al\original.mp4' --authorization-confirmed
```

La cabecera muestra el monograma CW separado de un nombre legible. WhatsApp usa
un pictograma reconocible sobre verde; en móvil hay accesos fijos a WhatsApp y
llamada, y un menú de pantalla completa. Los mensajes de WhatsApp incorporan el
servicio o caso consultado cuando se conoce, sin inventar datos del cliente.

## Repositorio y preparación para PythonAnywhere

El repositorio contiene `public_media/` con solo los nueve derivados web
autorizados. No incluye la base de datos local, originales 4K, adjuntos privados,
`media/`, `.env`, el entorno virtual ni archivos recopilados. En una instalación
nueva, después de `migrate`, ejecute una vez:

```bash
python manage.py seed_public_cw_media --authorization-confirmed
python manage.py collectstatic --noinput
```

El primer comando comprueba la firma y SHA-256 de cada derivado, instala dos
casos reales y la presentación de marca en la base de datos, y copia únicamente
los archivos públicos a `MEDIA_ROOT`. Es idempotente; no requiere ni fabrica los
originales privados. Configure en la pestaña Web de PythonAnywhere los mapeos
`/static/` → el `STATIC_ROOT` absoluto y `/media/` → el `MEDIA_ROOT` absoluto.
Nunca sirva `private_uploads/` como ruta estática.

Este proyecto usa Django 6.1 y Pillow 12.3, y requiere Python 3.12 o superior; compruebe la
imagen del sistema de la cuenta y elija la misma versión de Python para la web
y su virtualenv. Configure el WSGI de la pestaña Web para importar
`cvww_proyect.settings` desde el directorio que contiene `manage.py`. Inyecte
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` y
otros valores reales fuera de Git, tanto en WSGI como en la consola de gestión.
Antes de exponer el formulario, resuelva los datos legales y el plan de copias
de seguridad indicados en [BUSINESS_DATA_PENDING.md](BUSINESS_DATA_PENDING.md).
Una subida a GitHub no constituye una publicación ni una validación en vivo.
Referencias: [despliegue Django](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject),
[archivos estáticos y media](https://help.pythonanywhere.com/pages/DjangoStaticFiles) y
[versiones de Python](https://help.pythonanywhere.com/pages/PythonVersions).

Para generar nuevos derivados sin sobrescribir archivos existentes:

```powershell
.\Tools\convert-portfolio-video.ps1 -Source 'C:\ruta\original.mp4' -OutputName 'caso-descriptivo' -PreviewStart 6 -PosterAt 10
```

El script usa `ffmpeg` de PATH o `imageio-ffmpeg` instalado solo en el entorno
virtual de procesamiento; no es dependencia de producción. Inspeccione el clip
completo y confirme autorización, contexto técnico y privacidad antes de
publicarlo desde el admin. La gestión pública de videos requiere póster,
preview, versión completa optimizada y estado `Autorizado`.

Para múltiples procesos o servidores, sustituya la caché local por una caché
compartida para que el rate limit sea global. Verifique el IP entregado por el
proxy, defina retención y análisis antimalware, y asegure persistencia/backup de
base de datos, `media/` y `private_uploads/` antes de abrir el formulario al público.

### Despliegue seguro en PythonAnywhere

Antes de recargar la aplicación, cree y seleccione un entorno virtual real:

```bash
python3.13 -m venv /home/CWreparaciones/.virtualenvs/cw-reparaciones
source /home/CWreparaciones/.virtualenvs/cw-reparaciones/bin/activate
cd /home/CWreparaciones/CW-Reparaciones
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

En la pestaña **Web**, configure el campo Virtualenv con
`/home/CWreparaciones/.virtualenvs/cw-reparaciones`. En PythonAnywhere también
debe definir `DJANGO_TRUST_X_REAL_IP=true`, porque el proxy entrega la IP del
visitante mediante `X-Real-IP`; el valor permanece desactivado por defecto para
que esa cabecera no pueda falsificarse en otros proveedores. Active
`DJANGO_TRUST_PROXY_SSL_HEADER=true` solo después de verificar que HTTPS se
detecta correctamente y no produce un bucle de redirecciones.

La migración `0009_securityratelimitbucket` debe ejecutarse antes del Reload:
comparte los límites del formulario y del login administrativo entre todos los
workers sin guardar IP ni usuario en texto legible. El acceso administrativo se
limita de forma independiente por IP, cuenta objetivo y combinación IP-cuenta,
para cubrir tanto fuerza bruta local como distribuida. Haga una copia de
`db.sqlite3` y `private_uploads/` antes de migrar. Puede cambiar la ruta visible
del administrador con `DJANGO_ADMIN_URL`; esto reduce escaneo automatizado, pero
no sustituye contraseña única, gestor de contraseñas ni MFA de la cuenta de
hosting.

La aplicación aplica CSP estricta con nonce, sesiones de ocho horas cerradas al
salir del navegador, cookies `__Host-` bajo HTTPS, límites de cuerpo/archivos,
validación decodificada de imágenes y estructura MP4. El proxy web sigue siendo
la capa correcta para fijar un límite total del cuerpo antes de que llegue a
Django. Para adjuntos de clientes se recomienda además análisis antimalware y
una política operativa de retención/borrado.

## Variables de entorno

Copie `.env.example` como referencia y configure las variables en el proveedor
de despliegue. Django no carga archivos `.env` automáticamente: así se evita una
dependencia adicional y el entorno de producción puede inyectar secretos de
forma nativa.

Como mínimo en producción:

- `DJANGO_DEBUG=false`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_TIME_ZONE=America/Bogota`
- `DJANGO_TRUST_X_REAL_IP=true` en PythonAnywhere
- `DJANGO_TRUST_PROXY_SSL_HEADER=true` después de validar HTTPS
- destinatario, remitente y credenciales SMTP si se habilitan notificaciones

No active HSTS con subdominios o preload hasta confirmar que todo el dominio se
sirve exclusivamente por HTTPS.

## Validación

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Para una comprobación de despliegue, ejecute `check --deploy` con las variables
reales de producción. Ninguna comprobación local sustituye una prueba posterior
en el dominio final.

## Activos de marca

La mascota incluida es un recurso decorativo derivado de la referencia visual
entregada. No representa un técnico real ni un trabajo realizado. Sustitúyala
por el PNG/WebP oficial cuando la marca entregue el original; el diseño no
requiere reconstrucción para hacerlo. Las capturas de Instagram de 2024 no se
publican como fotografías de trabajos.

El nuevo `cw-mark.svg` es una versión vectorial simplificada del monograma
aportado, pensada para tamaños pequeños; el archivo de logo previo se conserva.
