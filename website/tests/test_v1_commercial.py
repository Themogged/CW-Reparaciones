import json
import re
from html import unescape
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from website.models import (
    Brand,
    BrandVideo,
    CoverageZone,
    PortfolioProject,
    PortfolioVideo,
    Service,
    ServiceBrand,
    ServiceRequest,
    SiteSettings,
)


class CommercialV1Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.site = SiteSettings.objects.get(pk=1)

    def test_confirmed_contact_catalog_and_coverage_are_available(self):
        self.assertEqual(self.site.whatsapp_url, "https://wa.me/573175040053")
        self.assertEqual(self.site.timezone, "America/Bogota")
        self.assertEqual(Service.objects.count(), 8)
        self.assertIn("Bello", CoverageZone.objects.values_list("name", flat=True))
        for slug in ("lavadoras", "neveras", "lavadoras-industriales"):
            with self.subTest(slug=slug):
                self.assertEqual(
                    self.client.get(reverse("website:service_detail", args=(slug,))).status_code,
                    200,
                )
        self.assertEqual(self.client.get(reverse("website:coverage")).status_code, 200)

    def test_business_structured_data_uses_current_confirmed_values(self):
        def business_data():
            response = self.client.get(reverse("website:home"))
            match = re.search(
                r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                response.content.decode("utf-8"),
                re.DOTALL,
            )
            self.assertIsNotNone(match)
            return json.loads(match.group(1))

        data = business_data()
        self.assertEqual(data["telephone"], "+57 317 504 0053")
        self.assertIn("Bello", [zone["name"] for zone in data["areaServed"]])
        self.site.phone = ""
        self.site.email = ""
        self.site.save()
        CoverageZone.objects.filter(name="Bello").update(is_confirmed=False)
        data = business_data()
        self.assertNotIn("telephone", data)
        self.assertNotIn("email", data)
        self.assertNotIn("Bello", [zone["name"] for zone in data["areaServed"]])

    def test_header_and_mobile_dock_use_page_specific_whatsapp_message(self):
        response = self.client.get(reverse("website:service_detail", args=("lavadoras",)))
        html = response.content.decode("utf-8")
        self.assertIn("cw-mark.svg", html)
        self.assertIn("<strong>CW Reparaciones</strong>", html)
        header = re.search(r'<a class="header-whatsapp" href="([^"]+)"', html)
        dock = re.search(r'<a class="sticky-action sticky-whatsapp" href="([^"]+)"', html)
        self.assertIsNotNone(header)
        self.assertIsNotNone(dock)
        self.assertEqual(unescape(header.group(1)), unescape(dock.group(1)))
        message = parse_qs(urlparse(unescape(header.group(1))).query)["text"][0]
        self.assertIn("revisar mi lavadora", message)
        self.assertEqual(len(re.findall(r'class="sticky-action(?: |")', html)), 2)

    def test_reference_brand_is_not_public_until_support_is_verified(self):
        service = Service.objects.get(slug="lavadoras")
        brand = Brand.objects.get(name="Samsung")
        link = ServiceBrand.objects.create(
            service=service, brand=brand, supported=True, verified=False
        )
        response = self.client.get(service.get_absolute_url())
        self.assertNotContains(response, "Marcas confirmadas")
        link.verified = True
        link.save()
        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, "Marcas confirmadas")
        self.assertContains(response, "Samsung")
        self.assertContains(response, "no implica ser un centro autorizado")

    def test_portfolio_hides_drafts_and_requires_authorization(self):
        self.site.feature_portfolio = True
        self.site.save()
        project = PortfolioProject.objects.create(
            title="Caso de prueba autorizado",
            slug="caso-de-prueba-autorizado",
            authorization_status=PortfolioProject.AuthorizationStatus.PENDING,
            is_published=False,
        )
        detail_url = reverse("website:portfolio_detail", args=(project.slug,))
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        project.is_published = True
        with self.assertRaises(ValidationError):
            project.full_clean()
        project.authorization_status = PortfolioProject.AuthorizationStatus.AUTHORIZED
        project.full_clean()
        project.save()
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_video_cannot_publish_without_web_assets(self):
        project = PortfolioProject.objects.create(
            title="Caso autorizado",
            authorization_status=PortfolioProject.AuthorizationStatus.AUTHORIZED,
            is_published=True,
        )
        video = PortfolioVideo(
            project=project,
            title="Registro del trabajo",
            authorization_status=PortfolioVideo.AuthorizationStatus.AUTHORIZED,
            is_published=True,
        )
        with self.assertRaises(ValidationError) as raised:
            video.full_clean()
        for field in ("preview_video", "full_video", "poster_image"):
            self.assertIn(field, raised.exception.message_dict)

    def test_video_metadata_only_exposes_authorized_public_derivatives(self):
        self.site.feature_portfolio = True
        self.site.save()
        project = PortfolioProject.objects.create(
            title="Caso documentado",
            authorization_status=PortfolioProject.AuthorizationStatus.AUTHORIZED,
            is_published=True,
        )
        PortfolioVideo.objects.create(
            project=project,
            title="Trabajo autorizado",
            description="Registro técnico </script><script>alert(1)</script>",
            original_video="portfolio_originals/private.mp4",
            preview_video="website/portfolio/previews/public.mp4",
            full_video="website/portfolio/full/public.mp4",
            poster_image="website/portfolio/posters/public.jpg",
            duration_seconds=58,
            authorization_status=PortfolioVideo.AuthorizationStatus.AUTHORIZED,
            is_published=True,
        )
        PortfolioVideo.objects.create(
            project=project,
            title="Video sin autorizar",
            preview_video="website/portfolio/previews/draft.mp4",
            full_video="website/portfolio/full/draft.mp4",
            poster_image="website/portfolio/posters/draft.jpg",
            is_published=False,
        )
        response = self.client.get(reverse("website:portfolio_detail", args=(project.slug,)))
        scripts = re.findall(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
            response.content.decode("utf-8"),
            re.DOTALL,
        )
        self.assertEqual(len(scripts), 1)
        data = json.loads(scripts[0])
        self.assertEqual(data["@type"], "VideoObject")
        self.assertEqual(data["duration"], "PT58S")
        self.assertEqual(data["name"], "Trabajo autorizado")
        self.assertEqual(data["contentUrl"], "http://testserver/media/website/portfolio/full/public.mp4")
        self.assertEqual(data["thumbnailUrl"], "http://testserver/media/website/portfolio/posters/public.jpg")
        self.assertIn("</script>", data["description"])
        self.assertNotIn("</script>", scripts[0])
        self.assertNotIn("portfolio_originals/private.mp4", response.content.decode("utf-8"))
        self.assertNotContains(response, "Video sin autorizar")

    def test_brand_video_requires_authorization_and_is_not_a_repair_case(self):
        video = BrandVideo.objects.create(title="Video de presentación")
        video.is_published = True
        with self.assertRaises(ValidationError) as raised:
            video.full_clean()
        for field in ("authorization_status", "preview_video", "full_video", "poster_image"):
            self.assertIn(field, raised.exception.message_dict)
        video.preview_video = "website/brand/previews/promo.mp4"
        video.full_video = "website/brand/full/promo.mp4"
        video.poster_image = "website/brand/posters/promo.jpg"
        video.authorization_status = BrandVideo.AuthorizationStatus.AUTHORIZED
        video.clean()
        video.save()
        self.assertIsNotNone(video.published_at)

        home = self.client.get(reverse("website:home"))
        about = self.client.get(reverse("website:about"))
        self.assertContains(home, "CW Reparaciones también en video")
        self.assertContains(about, "Video de presentación")
        self.assertNotContains(self.client.get(reverse("website:portfolio_list")), "Video de presentación")
        scripts = re.findall(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
            about.content.decode("utf-8"),
            re.DOTALL,
        )
        self.assertEqual(json.loads(scripts[0])["contentUrl"], "http://testserver/media/website/brand/full/promo.mp4")
        video.authorization_status = BrandVideo.AuthorizationStatus.REJECTED
        video.is_published = False
        video.save()
        self.assertNotContains(self.client.get(reverse("website:home")), "CW Reparaciones también en video")
        self.assertNotContains(self.client.get(reverse("website:about")), "Video de presentación")

    def test_valid_request_generates_ticket_without_unconfigured_email(self):
        data = {
            "service": str(Service.objects.get(slug="lavadoras").pk),
            "equipment": "Lavadora",
            "issue": "No enciende",
            "frequency": ServiceRequest.Frequency.UNKNOWN,
            "description": "No inicia al presionar el botón de encendido.",
            "municipality": "Bello",
            "name": "Prueba local",
            "whatsapp": "+57 317 504 0053",
            "phone": "",
            "email": "",
            "contact_preference": ServiceRequest.ContactPreference.WHATSAPP,
            "privacy_accepted": "on",
            "website": "",
        }
        with patch("website.views.send_mail") as send_mail:
            response = self.client.post(reverse("website:request_service"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        request = ServiceRequest.objects.get()
        self.assertTrue(request.ticket_number.startswith("CW-"))
        self.assertEqual(request.municipality, "Bello")
        send_mail.assert_not_called()
        success = self.client.get(response.url)
        self.assertContains(success, request.ticket_number)
        self.assertEqual(success["X-Robots-Tag"], "noindex, nofollow")
