import re

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from website.models import (
    SecurityRateLimitBucket,
    Service,
    ServiceCategory,
    ServiceRequest,
)
from website.upload_handlers import ServiceRequestUploadHandler
from website.validators import MAX_IMAGE_SIZE

from .test_validators import VALID_PNG


class SecurityHeaderTests(TestCase):
    def test_public_html_has_strict_browser_security_headers(self):
        response = self.client.get(reverse("website:home"))

        self.assertEqual(response.status_code, 200)
        policy = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("script-src-attr 'none'", policy)
        self.assertNotIn("'unsafe-inline'", policy)
        self.assertRegex(policy, r"'nonce-[A-Za-z0-9_-]+'")
        nonce = re.search(r"'nonce-([A-Za-z0-9_-]+)'", policy).group(1)
        self.assertContains(response, f'nonce="{nonce}"')
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(response.headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertIn("camera=()", response.headers["Permissions-Policy"])

    @override_settings(ALLOWED_HOSTS=["cwreparaciones.pythonanywhere.com"])
    def test_untrusted_host_is_rejected(self):
        response = self.client.get("/", HTTP_HOST="cwreparaciones.pythonanywhere.com.evil.example")
        self.assertEqual(response.status_code, 400)

    def test_success_page_is_never_cached(self):
        response = self.client.get(reverse("website:request_success"))
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")


class CsrfAndCookieTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        category = ServiceCategory.objects.get(slug="hogar")
        self.service = Service.objects.create(
            category=category,
            name="Servicio seguridad",
            slug="servicio-seguridad",
            is_active=True,
        )

    def submission(self):
        return {
            "service": self.service.pk,
            "equipment": "Lavadora",
            "issue": "No enciende",
            "frequency": ServiceRequest.Frequency.UNKNOWN,
            "description": "Descripción de seguridad.",
            "name": "Persona",
            "whatsapp": "+57 300 123 4567",
            "municipality": "Bello",
            "contact_preference": ServiceRequest.ContactPreference.WHATSAPP,
            "privacy_accepted": "on",
        }

    def test_post_without_csrf_token_is_rejected(self):
        response = self.client.post(reverse("website:submit_request"), self.submission())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertFalse(SecurityRateLimitBucket.objects.exists())

    def test_untrusted_origin_is_rejected_even_with_token(self):
        form_response = self.client.get(reverse("website:request_service"))
        token = form_response.cookies[settings.CSRF_COOKIE_NAME].value
        data = self.submission()
        data["csrfmiddlewaretoken"] = token
        response = self.client.post(
            reverse("website:submit_request"),
            data,
            HTTP_ORIGIN="https://evil.example",
            secure=True,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ServiceRequest.objects.exists())

    @override_settings(
        CSRF_COOKIE_SECURE=True,
        CSRF_COOKIE_HTTPONLY=True,
        CSRF_COOKIE_SAMESITE="Lax",
    )
    def test_csrf_cookie_uses_secure_flags(self):
        response = self.client.get(reverse("website:request_service"), secure=True)
        cookie = response.cookies[settings.CSRF_COOKIE_NAME]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")


class AbuseProtectionTests(TestCase):
    def test_admin_post_without_csrf_does_not_consume_login_limit(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("admin:login"),
            {"username": "unknown", "password": "incorrect"},
            REMOTE_ADDR="192.0.2.79",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SecurityRateLimitBucket.objects.exists())

    @override_settings(
        WEBSITE_ADMIN_LOGIN_IP_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_USER_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_PAIR_LIMIT=1,
        WEBSITE_ADMIN_LOGIN_WINDOW=60,
    )
    def test_admin_login_is_rate_limited(self):
        url = reverse("admin:login")
        payload = {"username": "unknown", "password": "incorrect"}
        first = self.client.post(url, payload, REMOTE_ADDR="192.0.2.80")
        second = self.client.post(url, payload, REMOTE_ADDR="192.0.2.80")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn("no-store", second.headers["Cache-Control"])
        self.assertGreaterEqual(int(second.headers["Retry-After"]), 1)

    @override_settings(
        WEBSITE_ADMIN_LOGIN_IP_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_USER_LIMIT=2,
        WEBSITE_ADMIN_LOGIN_PAIR_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_WINDOW=60,
    )
    def test_admin_username_limit_cannot_be_bypassed_by_changing_ip(self):
        url = reverse("admin:login")
        payload = {"username": "target-account", "password": "incorrect"}

        first = self.client.post(url, payload, REMOTE_ADDR="192.0.2.91")
        second = self.client.post(url, payload, REMOTE_ADDR="192.0.2.92")
        third = self.client.post(url, payload, REMOTE_ADDR="192.0.2.93")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(
            SecurityRateLimitBucket.objects.filter(scope="admin-login-user").count(),
            1,
        )

    @override_settings(
        WEBSITE_ADMIN_LOGIN_IP_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_USER_LIMIT=1,
        WEBSITE_ADMIN_LOGIN_PAIR_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_WINDOW=60,
    )
    def test_admin_username_limit_normalizes_equivalent_unicode(self):
        url = reverse("admin:login")
        first = self.client.post(
            url,
            {"username": "target", "password": "incorrect"},
            REMOTE_ADDR="192.0.2.94",
        )
        second = self.client.post(
            url,
            {"username": "ｔａｒｇｅｔ", "password": "incorrect"},
            REMOTE_ADDR="192.0.2.95",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    @override_settings(
        WEBSITE_ADMIN_LOGIN_IP_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_USER_LIMIT=20,
        WEBSITE_ADMIN_LOGIN_PAIR_LIMIT=2,
        WEBSITE_ADMIN_LOGIN_WINDOW=60,
    )
    def test_blocked_ip_username_pair_does_not_exhaust_global_user_limit(self):
        url = reverse("admin:login")
        payload = {"username": "target-account", "password": "incorrect"}
        responses = [
            self.client.post(url, payload, REMOTE_ADDR="192.0.2.96")
            for _ in range(5)
        ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 429, 429, 429])
        user_bucket = SecurityRateLimitBucket.objects.get(scope="admin-login-user")
        self.assertEqual(user_bucket.count, 2)

    def test_too_many_uploaded_files_are_rejected_before_form_validation(self):
        response = self.client.post(
            reverse("website:submit_request"),
            {
                "first": SimpleUploadedFile("one.png", VALID_PNG, content_type="image/png"),
                "second": SimpleUploadedFile("two.png", VALID_PNG, content_type="image/png"),
            },
            REMOTE_ADDR="192.0.2.81",
        )
        self.assertEqual(response.status_code, 400)

    def test_oversized_upload_is_rejected_before_being_buffered(self):
        handler = ServiceRequestUploadHandler()
        with self.assertRaises(RequestDataTooBig):
            handler.new_file(
                "diagnostic_media",
                "large.png",
                "image/png",
                MAX_IMAGE_SIZE + 1,
            )
