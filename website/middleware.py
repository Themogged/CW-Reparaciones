from __future__ import annotations

import logging
import unicodedata

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.urls import NoReverseMatch, reverse
from django.utils.deprecation import MiddlewareMixin

from .rate_limits import consume_rate_limit, get_remote_address
from .upload_handlers import ServiceRequestUploadHandler


logger = logging.getLogger("website.security")


def _normalized_login_username(value: object) -> str:
    """Replica la normalización NFKC del formulario de autenticación de Django."""

    raw_username = str(value or "").strip()
    if not raw_username:
        return "<empty>"
    # Django evita normalizar entradas ya inválidas y demasiado largas para no
    # amplificar trabajo con Unicode. Todas ellas comparten un único bucket.
    if len(raw_username) > 150:
        return "<overlong>"
    username = unicodedata.normalize("NFKC", raw_username)
    if len(username) > 150:
        return "<overlong>"
    return username.casefold()


class ServiceRequestUploadLimitMiddleware:
    """Instala límites de streaming antes de que CSRF analice el multipart."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST":
            try:
                request_path = reverse("website:submit_request")
            except NoReverseMatch:
                request_path = None
            if request_path and request.path_info == request_path:
                request.upload_handlers.insert(0, ServiceRequestUploadHandler(request))
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Añade controles de navegador que no cubre SecurityMiddleware."""

    permissions_policy = ", ".join(
        (
            "accelerometer=()",
            "autoplay=(self)",
            "camera=()",
            "display-capture=()",
            "encrypted-media=()",
            "fullscreen=(self)",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "payment=()",
            "publickey-credentials-get=()",
            "usb=()",
        )
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.headers.setdefault("Permissions-Policy", self.permissions_policy)
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Origin-Agent-Cluster", "?1")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if request.path_info.startswith(f"/{settings.ADMIN_URL}"):
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
            response.headers.setdefault("Cache-Control", "private, no-store")
        return response


class AdminLoginRateLimitMiddleware(MiddlewareMixin):
    """Frena intentos por IP, cuenta objetivo y combinación IP-cuenta."""

    @staticmethod
    def _admin_login_path() -> str | None:
        try:
            return reverse("admin:login")
        except NoReverseMatch:
            return None

    @staticmethod
    def _limited_response(retry_after: int) -> HttpResponse:
        response = HttpResponse(
            "Demasiados intentos de acceso. Inténtalo nuevamente más tarde.",
            status=429,
            content_type="text/plain; charset=utf-8",
        )
        response["Retry-After"] = str(max(1, retry_after))
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    def process_view(self, request: HttpRequest, view_func, view_args, view_kwargs):
        del view_func, view_args, view_kwargs
        login_path = self._admin_login_path()
        if request.method == "POST" and login_path and request.path_info == login_path:
            address = get_remote_address(request)
            window = settings.WEBSITE_ADMIN_LOGIN_WINDOW
            ip_result = consume_rate_limit(
                scope="admin-login-ip",
                identity=address,
                limit=settings.WEBSITE_ADMIN_LOGIN_IP_LIMIT,
                window_seconds=window,
            )

            username = _normalized_login_username(request.POST.get("username", ""))
            result = ip_result
            if not result.limited:
                result = consume_rate_limit(
                    scope="admin-login-pair",
                    identity=f"{address}\x00{username}",
                    limit=settings.WEBSITE_ADMIN_LOGIN_PAIR_LIMIT,
                    window_seconds=window,
                )
            if not result.limited:
                result = consume_rate_limit(
                    scope="admin-login-user",
                    identity=username,
                    limit=settings.WEBSITE_ADMIN_LOGIN_USER_LIMIT,
                    window_seconds=window,
                )

            if result.limited:
                if result.count == result.limit + 1:
                    logger.warning("Se activó el límite de intentos del acceso administrativo.")
                return self._limited_response(result.retry_after_seconds)
        return None
