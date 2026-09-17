from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import SecurityRateLimitBucket


@dataclass(frozen=True)
class RateLimitResult:
    limited: bool
    count: int
    limit: int
    window_seconds: int
    retry_after_seconds: int


def _normalized_ip(value: object) -> str | None:
    try:
        return ipaddress.ip_address(str(value or "").strip()).compressed
    except ValueError:
        return None


def get_remote_address(request: HttpRequest) -> str:
    """Obtiene la IP sin confiar por defecto en cabeceras del cliente.

    PythonAnywhere reemplaza ``X-Real-IP`` en su proxy. Su uso es explícito para
    no convertir esa cabecera en una vía de evasión al desplegar en otro host.
    """

    if getattr(settings, "WEBSITE_TRUST_X_REAL_IP", False):
        trusted_address = _normalized_ip(request.META.get("HTTP_X_REAL_IP"))
        if trusted_address:
            return trusted_address

    return _normalized_ip(request.META.get("REMOTE_ADDR")) or "unknown"


def _bucket_key(scope: str, identity: str) -> str:
    # Un volcado de la tabla no revela IP ni usuario mediante una búsqueda directa.
    return salted_hmac(
        "website.security.rate-limit",
        f"{scope}\x00{identity}",
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def consume_rate_limit(
    *, scope: str, identity: str, limit: int, window_seconds: int
) -> RateLimitResult:
    """Incrementa un contador persistente compartido por todos los workers WSGI."""

    normalized_limit = max(1, int(limit))
    normalized_window = max(60, int(window_seconds))
    now = timezone.now()
    new_expiry = now + timedelta(seconds=normalized_window)
    key = _bucket_key(scope, identity)

    active_update = SecurityRateLimitBucket.objects.filter(
        pk=key, expires_at__gt=now
    ).update(count=F("count") + 1)

    if active_update:
        bucket = SecurityRateLimitBucket.objects.only("count", "expires_at").get(pk=key)
        count = bucket.count
        expires_at = bucket.expires_at
    else:
        reset_update = SecurityRateLimitBucket.objects.filter(
            pk=key, expires_at__lte=now
        ).update(scope=scope, count=1, expires_at=new_expiry)

        if reset_update:
            count = 1
            expires_at = new_expiry
        else:
            try:
                # El savepoint permite continuar si otro worker crea la misma
                # fila entre la comprobación y el INSERT.
                with transaction.atomic():
                    SecurityRateLimitBucket.objects.create(
                        key=key,
                        scope=scope,
                        count=1,
                        expires_at=new_expiry,
                    )
                count = 1
                expires_at = new_expiry
            except IntegrityError:
                SecurityRateLimitBucket.objects.filter(
                    pk=key, expires_at__gt=now
                ).update(count=F("count") + 1)
                bucket = SecurityRateLimitBucket.objects.only(
                    "count", "expires_at"
                ).get(pk=key)
                count = bucket.count
                expires_at = bucket.expires_at

        # La tabla conserva una sola fila por identidad y elimina ventanas viejas.
        SecurityRateLimitBucket.objects.filter(expires_at__lte=now).exclude(
            pk=key
        ).delete()

    retry_after = max(1, math.ceil((expires_at - now).total_seconds()))
    return RateLimitResult(
        limited=count > normalized_limit,
        count=count,
        limit=normalized_limit,
        window_seconds=normalized_window,
        retry_after_seconds=retry_after,
    )


def consume_service_request_limit(request: HttpRequest) -> RateLimitResult:
    return consume_rate_limit(
        scope="service-request",
        identity=get_remote_address(request),
        limit=getattr(settings, "WEBSITE_REQUEST_RATE_LIMIT", 5),
        window_seconds=getattr(
            settings, "WEBSITE_REQUEST_RATE_LIMIT_WINDOW", 15 * 60
        ),
    )
