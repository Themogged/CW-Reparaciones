from django.db import OperationalError, ProgrammingError
from django.templatetags.static import static
from django.urls import reverse

from .models import PortfolioProject, SiteSettings


def site_context(request):
    """Expone solo canales realmente configurados a las plantillas públicas."""

    try:
        site_settings = SiteSettings.load()
    except (OperationalError, ProgrammingError):
        # Permite que páginas de error y collectstatic funcionen antes de migrar.
        site_settings = SiteSettings(pk=1)
    contact_channels = {}

    if site_settings.phone and site_settings.phone_url:
        contact_channels.update(
            {"phone": site_settings.phone, "phone_url": site_settings.phone_url}
        )
    if site_settings.whatsapp and site_settings.whatsapp_url:
        contact_channels.update(
            {
                "whatsapp": site_settings.whatsapp,
                "whatsapp_url": site_settings.whatsapp_url,
            }
        )
    if site_settings.email and site_settings.email_url:
        contact_channels.update(
            {"email": site_settings.email, "email_url": site_settings.email_url}
        )

    social_links = {
        name: url
        for name, url in (
            ("instagram", site_settings.instagram),
            ("facebook", site_settings.facebook),
            ("tiktok", site_settings.tiktok),
            ("youtube", site_settings.youtube),
        )
        if url
    }
    business_hours = [
        (label, value)
        for label, value in (
            ("Lunes a viernes", site_settings.hours_monday_friday),
            ("Sábado", site_settings.hours_saturday),
            ("Domingo", site_settings.hours_sunday),
        )
        if value
    ]

    try:
        canonical_url = request.build_absolute_uri(request.path)
        home_absolute_url = request.build_absolute_uri(reverse("website:home"))
        social_image_url = request.build_absolute_uri(
            static("website/images/cw-social-cover.png")
        )
    except (ValueError, RuntimeError):
        canonical_url = ""
        home_absolute_url = ""
        social_image_url = ""

    try:
        has_published_portfolio = bool(site_settings.feature_portfolio and PortfolioProject.objects.filter(
            is_published=True,
            authorization_status=PortfolioProject.AuthorizationStatus.AUTHORIZED,
        ).exists())
    except (OperationalError, ProgrammingError):
        has_published_portfolio = False

    return {
        "site_settings": site_settings,
        "contextual_whatsapp_url": site_settings.whatsapp_url_for(
            "Hola, vi la página de CW Reparaciones y necesito solicitar un servicio técnico."
        ),
        "contact_channels": contact_channels,
        "social_links": social_links,
        "business_hours": business_hours,
        "canonical_url": canonical_url,
        "home_absolute_url": home_absolute_url,
        "social_image_url": social_image_url,
        "has_published_portfolio": has_published_portfolio,
    }


# Alias compatible con una configuración anterior del context processor.
website_context = site_context
