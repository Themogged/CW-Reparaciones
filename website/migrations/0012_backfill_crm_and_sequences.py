import re
import unicodedata

from django.db import migrations


TICKET_PATTERN = re.compile(r"^CW-(\d{4})-(\d{6})$")


def normalize(value):
    normalized = unicodedata.normalize("NFKC", value or "").strip().casefold()
    if "@" in normalized:
        return "".join(normalized.split())
    digits = "".join(character for character in normalized if character.isdigit())
    if len(digits) == 12 and digits.startswith("57"):
        return digits[2:]
    return digits


def backfill_crm(apps, schema_editor):
    Customer = apps.get_model("website", "Customer")
    ServiceRequest = apps.get_model("website", "ServiceRequest")
    TicketSequence = apps.get_model("website", "TicketSequence")

    contact_map = {}
    for customer in Customer.objects.all().iterator():
        for value in (
            customer.normalized_phone,
            customer.normalized_whatsapp,
            customer.normalized_email,
        ):
            if value:
                contact_map.setdefault(value, customer.pk)

    for request in ServiceRequest.objects.filter(customer__isnull=True).iterator():
        normalized_phone = normalize(request.phone)
        normalized_whatsapp = normalize(request.whatsapp)
        normalized_email = normalize(request.email)
        keys = [value for value in (normalized_phone, normalized_whatsapp, normalized_email) if value]
        customer_id = next((contact_map[key] for key in keys if key in contact_map), None)
        if customer_id is None:
            customer = Customer.objects.create(
                name=request.name,
                phone=request.phone,
                whatsapp=request.whatsapp,
                email=request.email,
                municipality=request.municipality,
                sector=request.sector,
                address=request.address,
                normalized_phone=normalized_phone,
                normalized_whatsapp=normalized_whatsapp,
                normalized_email=normalized_email,
            )
            customer_id = customer.pk
            for key in keys:
                contact_map.setdefault(key, customer_id)
        ServiceRequest.objects.filter(pk=request.pk).update(customer_id=customer_id)

    maxima = {}
    for ticket in ServiceRequest.objects.exclude(ticket_number__isnull=True).values_list("ticket_number", flat=True):
        match = TICKET_PATTERN.match(ticket or "")
        if match:
            year, value = int(match.group(1)), int(match.group(2))
            maxima[year] = max(maxima.get(year, 0), value)
    for year, maximum in maxima.items():
        TicketSequence.objects.update_or_create(
            year=year,
            defaults={"next_value": maximum + 1},
        )


class Migration(migrations.Migration):
    dependencies = [("website", "0011_login_history")]

    operations = [migrations.RunPython(backfill_crm, migrations.RunPython.noop)]
