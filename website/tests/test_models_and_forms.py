from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from website.forms import ServiceRequestForm
from website.models import (
    CustomerReview,
    FAQItem,
    Service,
    ServiceCategory,
    ServiceRequest,
    SiteSettings,
)

from .test_validators import VALID_PNG


class SeedDataTests(TestCase):
    def test_only_confirmed_categories_are_seeded(self):
        self.assertQuerySetEqual(
            ServiceCategory.objects.order_by("order").values_list("name", flat=True),
            ["Hogar", "Industrial"],
        )

    def test_safe_faq_content_is_seeded(self):
        self.assertEqual(FAQItem.objects.filter(service__isnull=True).count(), 6)
        combined = " ".join(FAQItem.objects.values_list("answer", flat=True))
        self.assertNotIn("garantía", combined.lower())
        self.assertNotIn("24/7", combined)


class SiteSettingsTests(TestCase):
    def test_defaults_keep_unconfirmed_modules_and_contacts_hidden(self):
        settings_object = SiteSettings()
        self.assertEqual(settings_object.brand_name, "CW Reparaciones")
        self.assertEqual(settings_object.phone, "+57 317 504 0053")
        self.assertEqual(settings_object.whatsapp, "+57 317 504 0053")
        self.assertEqual(settings_object.email, "charlesrodriguez2009@hotmail.com")
        self.assertEqual(settings_object.hours_monday_friday, "")
        self.assertFalse(settings_object.feature_portfolio)
        self.assertFalse(settings_object.feature_reviews)
        self.assertTrue(settings_object.feature_services)
        self.assertTrue(settings_object.feature_diagnostic_form)

    def test_save_enforces_singleton_primary_key(self):
        SiteSettings.objects.filter(pk=1).update(brand_name="Primera")
        SiteSettings(brand_name="Actualizada").save()
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.objects.get(pk=1).brand_name, "Actualizada")

    def test_contact_urls_exist_only_when_configured(self):
        settings_object = SiteSettings(
            phone="+593 99 123 4567",
            whatsapp="+593 99 123 4567",
            email="contacto@example.com",
        )
        self.assertEqual(settings_object.phone_url, "tel:+593991234567")
        self.assertEqual(settings_object.whatsapp_url, "https://wa.me/593991234567")
        self.assertEqual(settings_object.email_url, "mailto:contacto@example.com")

    def test_singleton_cannot_be_deleted_through_model(self):
        settings_object = SiteSettings.objects.get(pk=1)
        with self.assertRaises(ValidationError):
            settings_object.delete()


class ContentModelTests(TestCase):
    def test_service_generates_unique_slug_and_compatibility_attributes(self):
        category = ServiceCategory.objects.get(slug="hogar")
        first = Service.objects.create(
            category=category,
            name="Servicio técnico",
            description="Descripción larga",
            common_problems="No enciende\nHace ruido",
            process="Recepción\nEvaluación",
        )
        second = Service.objects.create(category=category, name="Servicio técnico")
        self.assertEqual(first.slug, "servicio-tecnico")
        self.assertEqual(second.slug, "servicio-tecnico-2")
        self.assertEqual(first.long_description, "Descripción larga")
        self.assertEqual(first.problems, ["No enciende", "Hace ruido"])
        self.assertEqual(first.process_steps, ["Recepción", "Evaluación"])

    def test_review_requires_rating_between_one_and_five(self):
        review = CustomerReview(display_name="Cliente real", quote="Texto", rating=6)
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_review_requires_verification_and_real_source_before_publication(self):
        review = CustomerReview(
            display_name="Cliente real",
            quote="Texto real",
            rating=5,
            is_published=True,
        )
        with self.assertRaises(ValidationError) as context:
            review.full_clean()
        self.assertIn("is_verified", context.exception.message_dict)
        self.assertIn("source", context.exception.message_dict)

        review.is_verified = True
        review.source = "Perfil verificado"
        review.full_clean()

    def test_request_requires_selected_contact_channel(self):
        service_request = ServiceRequest(
            equipment="Equipo",
            issue="No enciende",
            frequency=ServiceRequest.Frequency.UNKNOWN,
            description="Descripción suficiente",
            name="Persona",
            phone="0991234567",
            contact_preference=ServiceRequest.ContactPreference.EMAIL,
            privacy_accepted=True,
        )
        with self.assertRaises(ValidationError) as context:
            service_request.full_clean()
        self.assertIn("email", context.exception.message_dict)


class ServiceRequestFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "service": "",
            "equipment": "Electrodoméstico",
            "issue": "No enciende",
            "frequency": ServiceRequest.Frequency.INTERMITTENT,
            "description": "El equipo dejó de encender de forma intermitente.",
            "name": "Persona solicitante",
            "phone": "+593 99 123 4567",
            "whatsapp": "+593 99 123 4567",
            "municipality": "Bello",
            "email": "",
            "contact_preference": ServiceRequest.ContactPreference.PHONE,
            "privacy_accepted": "on",
            "source": "instagram",
            "utm_source": "instagram",
            "utm_medium": "social",
            "utm_campaign": "campana",
            "utm_content": "pieza-a",
            "utm_term": "reparacion",
            "website": "",
        }
        data.update(overrides)
        return data

    def test_valid_form_preserves_minimum_lead_and_attribution(self):
        form = ServiceRequestForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        service_request = form.save()
        self.assertEqual(service_request.source, "instagram")
        self.assertEqual(service_request.utm_medium, "social")
        self.assertIsNotNone(service_request.consented_at)

    def test_form_defines_seven_steps(self):
        form = ServiceRequestForm()
        steps = list(form.steps())
        self.assertEqual([number for number, fields in steps], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(steps[3][1][0].name, "diagnostic_media")

    def test_honeypot_rejects_submission(self):
        form = ServiceRequestForm(data=self.valid_data(website="spam.example"))
        self.assertFalse(form.is_valid())
        self.assertIn("website", form.errors)

    def test_privacy_consent_is_required(self):
        form = ServiceRequestForm(data=self.valid_data(privacy_accepted=""))
        self.assertFalse(form.is_valid())
        self.assertIn("privacy_accepted", form.errors)

    def test_phone_requires_real_digits(self):
        form = ServiceRequestForm(data=self.valid_data(phone="----------"))
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_email_preference_requires_email(self):
        form = ServiceRequestForm(
            data=self.valid_data(
                contact_preference=ServiceRequest.ContactPreference.EMAIL,
                email="",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_rejects_media_with_fake_header(self):
        upload = SimpleUploadedFile("damage.png", b"not-a-png", content_type="image/png")
        form = ServiceRequestForm(
            data=self.valid_data(), files={"diagnostic_media": upload}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("diagnostic_media", form.errors)

    def test_upload_widget_exposes_server_limits(self):
        attrs = ServiceRequestForm().fields["diagnostic_media"].widget.attrs
        self.assertEqual(attrs["data-max-image-bytes"], "8388608")
        self.assertEqual(attrs["data-max-video-bytes"], "20971520")
        self.assertIn("video/mp4", attrs["accept"])
