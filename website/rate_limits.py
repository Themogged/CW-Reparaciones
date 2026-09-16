from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest


@dataclass(frozen=True)
class RateLimitResult:
    limited: bool
    count: int
    limit: int
    window_seconds: int


def get_remote_address(request: HttpRequest) -> str:
    """Usa REMOTE_ADDR; no confía en cabeceras reenviadas por el cliente."""

    value = str(request.META.get("REMOTE_ADDR", "") or "").strip()
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        return "unknown"


def consume_service_request_limit(request: HttpRequest) -> RateLimitResult:
    limit = max(1, int(getattr(settings, "WEBSITE_REQUEST_RATE_LIMIT", 5)))
    window = max(
        60, int(getattr(settings, "WEBSITE_REQUEST_RATE_LIMIT_WINDOW", 15 * 60))
    )
    address_hash = hashlib.sha256(get_remote_address(request).encode("utf-8")).hexdigest()
    key = f"website:service-request:{address_hash}"

    if cache.add(key, 1, timeout=window):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=window)
            count = 1

    return RateLimitResult(
        limited=count > limit,
        count=count,
        limit=limit,
        window_seconds=window,
    )

