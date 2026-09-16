from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from website.context_processors import site_context
from website.models import SiteSettings
from website.rate_limits import consume_service_request_limit, get_remote_address


class ContextProcessorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_empty_contact_values_are_not_exposed_as_channels(self):
        SiteSettings.objects.filter(pk=1).update(phone="", whatsapp="", email="", instagram="")
        context = site_context(self.factory.get("/"))
        self.assertEqual(context["contact_channels"], {})
        self.assertEqual(context["social_links"], {})
        self.assertNotIn("Domingo", dict(context["business_hours"]))

    def test_configured_channels_and_metadata_are_exposed(self):
        SiteSettings.objects.filter(pk=1).update(
            phone="+593 99 123 4567", whatsapp="+593 99 123 4567", email="contacto@example.com"
        )
        context = site_context(self.factory.get("/contacto/", HTTP_HOST="testserver"))
        self.assertEqual(
            context["contact_channels"]["whatsapp_url"],
            "https://wa.me/593991234567",
        )
        self.assertEqual(context["contact_channels"]["phone_url"], "tel:+593991234567")
        self.assertEqual(
            context["contact_channels"]["email_url"],
            "mailto:contacto@example.com",
        )
        self.assertEqual(context["canonical_url"], "http://testserver/contacto/")
        self.assertTrue(context["social_image_url"].endswith("cw-social-cover.png"))


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def test_uses_remote_addr_and_ignores_forwarded_header(self):
        request = self.factory.post(
            "/solicitar-servicio/",
            REMOTE_ADDR="192.0.2.10",
            HTTP_X_FORWARDED_FOR="203.0.113.15",
        )
        self.assertEqual(get_remote_address(request), "192.0.2.10")

    @override_settings(WEBSITE_REQUEST_RATE_LIMIT=2, WEBSITE_REQUEST_RATE_LIMIT_WINDOW=60)
    def test_limits_after_configured_number_of_attempts(self):
        request = self.factory.post("/solicitar-servicio/", REMOTE_ADDR="192.0.2.20")
        self.assertFalse(consume_service_request_limit(request).limited)
        self.assertFalse(consume_service_request_limit(request).limited)
        result = consume_service_request_limit(request)
        self.assertTrue(result.limited)
        self.assertEqual(result.count, 3)
