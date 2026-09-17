from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def pythonanywhere_proxy_check(app_configs, **kwargs):
    del app_configs, kwargs
    is_pythonanywhere = any(
        host == ".pythonanywhere.com" or host.endswith(".pythonanywhere.com")
        for host in settings.ALLOWED_HOSTS
    )
    if not settings.DEBUG and is_pythonanywhere and not settings.WEBSITE_TRUST_X_REAL_IP:
        return [
            Warning(
                "PythonAnywhere requiere confiar explícitamente en X-Real-IP para "
                "aplicar límites por visitante.",
                hint="Defina DJANGO_TRUST_X_REAL_IP=true en el entorno WSGI.",
                id="website.W001",
            )
        ]
    return []
