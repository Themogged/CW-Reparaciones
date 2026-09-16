from django.db import migrations


CATEGORIES = (
    {
        "name": "Hogar",
        "slug": "hogar",
        "short_description": "Atención técnica para electrodomésticos de uso doméstico.",
        "order": 10,
    },
    {
        "name": "Negocios e industria",
        "slug": "negocios-e-industria",
        "short_description": "Atención técnica para electrodomésticos de uso industrial.",
        "order": 20,
    },
)

FAQS = (
    (
        "¿Qué tipo de equipos atienden?",
        "CW Reparaciones ofrece servicios técnicos para electrodomésticos domésticos e industriales.",
    ),
    (
        "¿Cómo solicito una revisión?",
        "Completa el formulario con los datos del equipo y una descripción del problema. La información se utilizará para atender tu solicitud.",
    ),
    (
        "¿Puedo enviar una foto del problema?",
        "Sí. Puedes adjuntar una foto para ayudarnos a entender mejor el problema. El formulario admite archivos JPEG, PNG y WebP.",
    ),
    (
        "¿Cómo puedo comunicarme?",
        "Puedes enviar el formulario de solicitud. Los demás canales de contacto se muestran únicamente cuando han sido configurados.",
    ),
    (
        "¿Cuál es el horario de atención?",
        "El horario confirmado es de lunes a viernes, de 7:00 AM a 5:00 PM, y los sábados, de 7:00 AM a 2:00 PM.",
    ),
    (
        "¿Atienden equipos industriales?",
        "Sí. CW Reparaciones ofrece servicios técnicos para electrodomésticos domésticos e industriales.",
    ),
)


def seed_confirmed_content(apps, schema_editor):
    ServiceCategory = apps.get_model("website", "ServiceCategory")
    FAQItem = apps.get_model("website", "FAQItem")

    for category_data in CATEGORIES:
        ServiceCategory.objects.get_or_create(
            name=category_data["name"],
            defaults={
                "slug": category_data["slug"],
                "short_description": category_data["short_description"],
                "order": category_data["order"],
                "is_active": True,
            },
        )

    for order, (question, answer) in enumerate(FAQS, start=10):
        FAQItem.objects.get_or_create(
            question=question,
            service=None,
            defaults={"answer": answer, "order": order, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [("website", "0001_initial")]

    operations = [
        migrations.RunPython(seed_confirmed_content, migrations.RunPython.noop),
    ]
