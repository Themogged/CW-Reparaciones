"""Django settings for the CW Reparaciones website.

Development defaults are intentionally convenient, while every sensitive or
deployment-specific value can be supplied through environment variables.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        f"{name} debe ser un booleano válido: true/false, yes/no, on/off o 1/0."
    )


def env_int(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    raw_value = os.getenv(name)
    try:
        value = default if raw_value is None else int(raw_value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} debe ser un número entero.") from exc
    if minimum is not None and value < minimum:
        raise ImproperlyConfigured(f"{name} debe ser mayor o igual a {minimum}.")
    if maximum is not None and value > maximum:
        raise ImproperlyConfigured(f"{name} debe ser menor o igual a {maximum}.")
    return value


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-local-development-only")
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1,[::1],testserver" if DEBUG else "",
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

development_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]", "testserver"}
if DEBUG and any(
    host not in development_hosts and not host.endswith(".localhost")
    for host in ALLOWED_HOSTS
):
    raise ImproperlyConfigured(
        "DJANGO_DEBUG=true solo puede usarse con hosts locales de desarrollo."
    )
if not DEBUG and SECRET_KEY == "django-insecure-local-development-only":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DJANGO_DEBUG=false.")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required when DJANGO_DEBUG=false.")
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-")):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY debe ser aleatoria, no predecible y tener al menos 50 caracteres."
    )
if not DEBUG and "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS no puede contener '*' en producción.")

ADMIN_URL = os.getenv("DJANGO_ADMIN_URL", "admin/").strip().strip("/")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_/-]{0,95}", ADMIN_URL or ""):
    raise ImproperlyConfigured("DJANGO_ADMIN_URL contiene caracteres no permitidos.")
ADMIN_URL = f"{ADMIN_URL}/"


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "website.apps.WebsiteConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "website.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "website.middleware.ServiceRequestUploadLimitMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "website.middleware.AdminLoginRateLimitMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cvww_proyect.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "website.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "cvww_proyect.wsgi.application"
ASGI_APPLICATION = "cvww_proyect.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "es"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "America/Bogota")
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750
FILE_UPLOAD_MAX_MEMORY_SIZE = 1_048_576
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_048_576
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 5

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "cw-reparaciones",
    }
}

WEBSITE_TRUST_X_REAL_IP = env_bool("DJANGO_TRUST_X_REAL_IP", False)
WEBSITE_REQUEST_RATE_LIMIT = env_int(
    "DJANGO_REQUEST_RATE_LIMIT", 5, minimum=1, maximum=100
)
WEBSITE_REQUEST_RATE_LIMIT_WINDOW = env_int(
    "DJANGO_REQUEST_RATE_LIMIT_WINDOW", 15 * 60, minimum=60, maximum=86_400
)
WEBSITE_ADMIN_LOGIN_IP_LIMIT = env_int(
    "DJANGO_ADMIN_LOGIN_IP_LIMIT", 20, minimum=3, maximum=1_000
)
WEBSITE_ADMIN_LOGIN_USER_LIMIT = env_int(
    "DJANGO_ADMIN_LOGIN_USER_LIMIT", 30, minimum=3, maximum=500
)
WEBSITE_ADMIN_LOGIN_PAIR_LIMIT = env_int(
    "DJANGO_ADMIN_LOGIN_PAIR_LIMIT", 8, minimum=3, maximum=100
)
WEBSITE_ADMIN_LOGIN_WINDOW = env_int(
    "DJANGO_ADMIN_LOGIN_WINDOW", 15 * 60, minimum=60, maximum=86_400
)


if DEBUG:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.console.EmailBackend",
        }
    }
else:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": os.getenv("DJANGO_EMAIL_HOST", "localhost"),
                "port": int(os.getenv("DJANGO_EMAIL_PORT", "587")),
                "username": os.getenv("DJANGO_EMAIL_HOST_USER") or None,
                "password": os.getenv("DJANGO_EMAIL_HOST_PASSWORD") or None,
                "use_tls": env_bool("DJANGO_EMAIL_USE_TLS", True),
                "use_ssl": env_bool("DJANGO_EMAIL_USE_SSL", False),
                "timeout": int(os.getenv("DJANGO_EMAIL_TIMEOUT", "10")),
            },
        }
    }
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "webmaster@localhost")
WEBSITE_CONTACT_TO_EMAIL = os.getenv("DJANGO_CONTACT_TO_EMAIL", "").strip()
# No se envía ningún correo con el remitente local o un servidor SMTP supuesto.
WEBSITE_EMAIL_NOTIFICATIONS_ENABLED = bool(
    WEBSITE_CONTACT_TO_EMAIL
    and os.getenv("DJANGO_DEFAULT_FROM_EMAIL")
    and os.getenv("DJANGO_EMAIL_HOST")
    and os.getenv("DJANGO_EMAIL_HOST_USER")
    and os.getenv("DJANGO_EMAIL_HOST_PASSWORD")
)


SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int(
    "DJANGO_SESSION_COOKIE_AGE", 8 * 60 * 60, minimum=300, maximum=7 * 24 * 60 * 60
)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_NAME = "__Host-cw_session" if SESSION_COOKIE_SECURE else "cw_session"
CSRF_COOKIE_NAME = "__Host-cw_csrf" if CSRF_COOKIE_SECURE else "cw_csrf"
SECURE_HSTS_SECONDS = env_int(
    "DJANGO_SECURE_HSTS_SECONDS",
    31_536_000 if not DEBUG else 0,
    minimum=0,
    maximum=63_072_000,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
if env_bool("DJANGO_TRUST_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "base-uri": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "font-src": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "frame-src": [CSP.NONE],
    "img-src": [CSP.SELF, "data:", "blob:"],
    "manifest-src": [CSP.SELF],
    "media-src": [CSP.SELF, "blob:"],
    "object-src": [CSP.NONE],
    "script-src": [CSP.SELF, CSP.NONCE],
    "script-src-attr": [CSP.NONE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "style-src-attr": [CSP.NONE],
    "worker-src": [CSP.SELF, "blob:"],
}
if not DEBUG:
    SECURE_CSP["upgrade-insecure-requests"] = True

URLIZE_ASSUME_HTTPS = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "website.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
