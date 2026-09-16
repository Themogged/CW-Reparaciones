from django.db import migrations
from django.utils.text import slugify


SERVICES = (
    ("lavadoras", "Lavadoras", "hogar"),
    ("neveras", "Neveras", "hogar"),
    ("estufas-induccion", "Estufas de inducción", "hogar"),
    ("lavavajillas", "Lavavajillas", "hogar"),
    ("aires-acondicionados", "Aires acondicionados", "hogar"),
    ("abanicos", "Abanicos / ventiladores", "hogar"),
    ("hornos-industriales", "Hornos industriales", "industriales"),
    ("lavadoras-industriales", "Lavadoras industriales", "industriales"),
)

ZONES = (
    ("Bello", "municipality"),
    ("Itagüí", "municipality"),
    ("El Poblado", "sector"),
    ("Sabaneta", "municipality"),
    ("La Estrella", "municipality"),
    ("Municipios aledaños", "to_confirm"),
    ("Corregimientos aledaños", "to_confirm"),
    ("Área Metropolitana", "area"),
)

BRANDS = (
    "Samsung", "LG", "Whirlpool", "Haceb", "Mabe", "Electrolux",
    "Challenger", "Bosch", "Siemens", "Panasonic", "Hisense", "Kalley",
    "General Electric", "Frigidaire", "Maytag", "Carrier", "Midea",
    "York", "Daikin", "Speed Queen", "Girbau", "Dexter", "Primus",
    "Rational", "Unox", "Hobart",
)

CONFIRMED_SETTINGS = {
    "brand_name": "CW Reparaciones",
    "tagline": "Servicios Técnicos",
    "phone": "+57 317 504 0053",
    "whatsapp": "+57 317 504 0053",
    "email": "charlesrodriguez2009@hotmail.com",
    "instagram": "https://www.instagram.com/cwreparaciones/",
    "country": "Colombia",
    "timezone": "America/Bogota",
}


def seed_cw_confirmed_v1(apps, schema_editor):
    SiteSettings = apps.get_model("website", "SiteSettings")
    ServiceCategory = apps.get_model("website", "ServiceCategory")
    Service = apps.get_model("website", "Service")
    CoverageZone = apps.get_model("website", "CoverageZone")
    Brand = apps.get_model("website", "Brand")
    FAQItem = apps.get_model("website", "FAQItem")
    ServiceRequest = apps.get_model("website", "ServiceRequest")

    site, created = SiteSettings.objects.get_or_create(pk=1, defaults=CONFIRMED_SETTINGS)
    if not created:
        changes = []
        for field, value in CONFIRMED_SETTINGS.items():
            if not getattr(site, field):
                setattr(site, field, value)
                changes.append(field)
        for field, old_value in (
            ("hours_monday_friday", "7:00 AM - 5:00 PM"),
            ("hours_saturday", "7:00 AM - 2:00 PM"),
        ):
            if getattr(site, field) == old_value:
                setattr(site, field, "")
                changes.append(field)
        if changes:
            site.save(update_fields=changes)

    industrial = ServiceCategory.objects.filter(
        slug="negocios-e-industria", name="Negocios e industria"
    ).first()
    if industrial:
        industrial.slug = "industriales"
        industrial.name = "Industrial"
        industrial.save(update_fields=("slug", "name"))
    industrial, _ = ServiceCategory.objects.get_or_create(
        slug="industriales",
        defaults={"name": "Industrial", "order": 20, "is_active": True},
    )
    home, _ = ServiceCategory.objects.get_or_create(
        slug="hogar",
        defaults={"name": "Hogar", "order": 10, "is_active": True},
    )
    category_ids = {"hogar": home.pk, "industriales": industrial.pk}
    for order, (slug, name, category) in enumerate(SERVICES, start=10):
        Service.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "category_id": category_ids[category],
                "short_description": f"Servicio técnico para {name.lower()}.",
                "order": order,
                "is_active": True,
                "is_featured": True,
            },
        )

    for order, (name, zone_type) in enumerate(ZONES, start=10):
        CoverageZone.objects.get_or_create(
            name=name,
            defaults={
                "slug": slugify(name),
                "zone_type": zone_type,
                "is_confirmed": True,
                "is_active": True,
                "order": order,
            },
        )

    for name in BRANDS:
        Brand.objects.get_or_create(name=name, defaults={"slug": slugify(name)})

    # El FAQ histórico afirmaba horarios no aportados por CW; no se publica.
    FAQItem.objects.filter(question="¿Cuál es el horario de atención?").update(is_active=False)
    FAQItem.objects.filter(
        question="¿Cómo puedo comunicarme?",
        answer="Puedes enviar el formulario de solicitud. Los demás canales de contacto se muestran únicamente cuando han sido configurados.",
    ).update(answer="Puedes escribirnos por WhatsApp, llamar o enviar una solicitud desde la web.")

    for lead in ServiceRequest.objects.filter(ticket_number__isnull=True).iterator():
        year = lead.created_at.year if lead.created_at else 2026
        lead.ticket_number = f"CW-{year}-{lead.pk.hex.upper()}"
        if lead.status == "in_review":
            lead.status = "diagnosis_pending"
        elif lead.status == "closed":
            lead.status = "completed"
        elif lead.status == "archived":
            lead.status = "cancelled"
        lead.save(update_fields=("ticket_number", "status"))


class Migration(migrations.Migration):
    dependencies = [("website", "0005_portfoliovideo_full_video_and_more")]

    operations = [migrations.RunPython(seed_cw_confirmed_v1, migrations.RunPython.noop)]
