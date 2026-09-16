from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from website.models import (
    CustomerReview,
    PortfolioProject,
    Service,
    ServiceCategory,
    ServiceRequest,
    SiteSettings,
)

from .test_validators import VALID_PNG


class PublicViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.settings_object = SiteSettings.objects.get(pk=1)
        self.category = ServiceCategory.objects.get(slug="hogar")
        self.active_service = Service.objects.create(
            category=self.category,
            name="Servicio visible",
            slug="servicio-visible",
            is_active=True,
        )
        self.inactive_service = Service.objects.create(
            category=self.category,
            name="Servicio oculto",
            slug="servicio-oculto",
            is_active=False,
        )

    def valid_submission(self, **overrides):
        data = {
            "service": self.active_service.pk,
            "equipment": "Electrodoméstico",
            "issue": "No enciende",
            "frequency": ServiceRequest.Frequency.UNKNOWN,
            "description": "Descripción del problema.",
            "name": "Persona solicitante",
            "phone": "+593 99 123 4567",
            "whatsapp": "+593 99 123 4567",
            "municipality": "Bello",
            "email": "",
            "contact_preference": ServiceRequest.ContactPreference.PHONE,
            "privacy_accepted": "on",
            "website": "",
            "source": "landing",
            "utm_source": "google",
            "utm_medium": "organic",
            "utm_campaign": "",
            "utm_content": "",
            "utm_term": "servicio tecnico",
        }
        data.update(overrides)
        return data

    def test_public_pages_render(self):
        route_names = (
            "home",
            "service_list",
            "process",
            "about",
            "contact",
            "privacy",
            "terms",
            "request_success",
        )
        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(f"website:{route_name}"))
                self.assertEqual(response.status_code, 200)

    def test_detail_hides_inactive_service(self):
        response = self.client.get(
            reverse("website:service_detail", args=(self.inactive_service.slug,))
        )
        self.assertEqual(response.status_code, 404)

    def test_prefetched_category_does_not_expose_inactive_services(self):
        response = self.client.get(reverse("website:service_list"))
        category = next(
            item
            for item in response.context["service_categories"]
            if item.pk == self.category.pk
        )
        self.assertIn(self.active_service, category.services.all())
        self.assertNotIn(self.inactive_service, category.services.all())

    def test_disabled_services_are_hidden_everywhere_and_detail_is_404(self):
        self.settings_object.feature_services = False
        self.settings_object.save()

        home_response = self.client.get(reverse("website:home"))
        contact_response = self.client.get(reverse("website:contact"))
        detail_response = self.client.get(
            reverse("website:service_detail", args=(self.active_service.slug,))
        )
        sitemap_response = self.client.get(reverse("website:sitemap"))

        self.assertFalse(home_response.context["services"].exists())
        self.assertFalse(home_response.context["service_categories"].exists())
        self.assertFalse(contact_response.context["services"].exists())
        self.assertFalse(
            contact_response.context["request_form"].fields["service"].queryset.exists()
        )
        self.assertEqual(detail_response.status_code, 404)
        self.assertNotContains(sitemap_response, "/servicios/", status_code=200)

    def test_home_only_exposes_enabled_real_proof(self):
        PortfolioProject.objects.create(
            title="Caso", authorization_status=PortfolioProject.AuthorizationStatus.AUTHORIZED, is_published=True
        )
        CustomerReview.objects.create(
            display_name="Cliente",
            quote="Reseña real",
            rating=5,
            source="Perfil verificado",
            is_verified=True,
            is_published=True,
        )
        response = self.client.get(reverse("website:home"))
        self.assertFalse(response.context["portfolio_projects"].exists())
        self.assertFalse(response.context["customer_reviews"].exists())

        self.settings_object.feature_portfolio = True
        self.settings_object.feature_reviews = True
        self.settings_object.save()
        response = self.client.get(reverse("website:home"))
        self.assertEqual(response.context["portfolio_projects"].count(), 1)
        self.assertEqual(response.context["customer_reviews"].count(), 1)

    def test_valid_submission_saves_minimum_data_and_utm(self):
        response = self.client.post(
            reverse("website:submit_request"),
            self.valid_submission(),
            REMOTE_ADDR="192.0.2.30",
        )
        self.assertRedirects(
            response, reverse("website:request_success"), fetch_redirect_response=False
        )
        service_request = ServiceRequest.objects.get()
        self.assertEqual(service_request.utm_source, "google")
        self.assertEqual(service_request.utm_term, "servicio tecnico")
        self.assertEqual(service_request.status, ServiceRequest.Status.NEW)
        self.assertTrue(service_request.privacy_accepted)
        self.assertIsNotNone(service_request.consented_at)

    def test_honeypot_returns_success_without_persisting(self):
        response = self.client.post(
            reverse("website:submit_request"),
            self.valid_submission(website="bot.example"),
            REMOTE_ADDR="192.0.2.31",
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_invalid_submission_returns_400(self):
        response = self.client.post(
            reverse("website:submit_request"),
            self.valid_submission(privacy_accepted=""),
            REMOTE_ADDR="192.0.2.32",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_disabled_form_returns_404(self):
        self.settings_object.feature_diagnostic_form = False
        self.settings_object.save()
        response = self.client.post(
            reverse("website:submit_request"),
            self.valid_submission(),
            REMOTE_ADDR="192.0.2.33",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(WEBSITE_REQUEST_RATE_LIMIT=1, WEBSITE_REQUEST_RATE_LIMIT_WINDOW=60)
    def test_submit_rate_limit_returns_429_and_retry_after(self):
        url = reverse("website:submit_request")
        first = self.client.post(
            url, self.valid_submission(), REMOTE_ADDR="192.0.2.34"
        )
        second = self.client.post(
            url, self.valid_submission(), REMOTE_ADDR="192.0.2.34"
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.headers["Retry-After"], "60")
        self.assertEqual(ServiceRequest.objects.count(), 1)

    def test_robots_and_sitemap_are_machine_readable(self):
        robots_response = self.client.get(reverse("website:robots"))
        sitemap_response = self.client.get(reverse("website:sitemap"))
        self.assertEqual(robots_response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(robots_response, reverse("website:sitemap"))
        self.assertEqual(sitemap_response["Content-Type"], "application/xml; charset=utf-8")
        self.assertContains(sitemap_response, self.active_service.get_absolute_url())


class PrivateAttachmentViewTests(TestCase):
    def setUp(self):
        self.media_field = ServiceRequest._meta.get_field("diagnostic_media")
        self.original_storage = self.media_field.storage
        self.media_field.storage = InMemoryStorage()
        self.service_request = ServiceRequest.objects.create(
            equipment="Equipo",
            issue="No enciende",
            frequency=ServiceRequest.Frequency.UNKNOWN,
            description="Descripción",
            diagnostic_media=SimpleUploadedFile(
                "damage.png", VALID_PNG, content_type="image/png"
            ),
            name="Persona",
            phone="0991234567",
            privacy_accepted=True,
        )

    def tearDown(self):
        self.media_field.storage = self.original_storage

    def test_anonymous_user_cannot_download_private_attachment(self):
        response = self.client.get(
            reverse(
                "website:request_attachment_download", args=(self.service_request.pk,)
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)

    def test_staff_without_request_permission_cannot_download(self):
        user = get_user_model().objects.create_user(
            username="staff", password="not-used", is_staff=True
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse(
                "website:request_attachment_download", args=(self.service_request.pk,)
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_authorized_staff_can_download_with_private_headers(self):
        user = get_user_model().objects.create_user(
            username="authorized-staff", password="not-used", is_staff=True
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="website", codename="view_servicerequest"
            )
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse(
                "website:request_attachment_download", args=(self.service_request.pk,)
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertEqual(response["Content-Security-Policy"], "sandbox; default-src 'none'")
        self.assertIn("attachment", response["Content-Disposition"])
