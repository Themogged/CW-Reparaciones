from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0008_brandvideo"),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityRateLimitBucket",
            fields=[
                (
                    "key",
                    models.CharField(
                        editable=False, max_length=64, primary_key=True, serialize=False
                    ),
                ),
                (
                    "scope",
                    models.CharField(db_index=True, editable=False, max_length=48),
                ),
                (
                    "count",
                    models.PositiveIntegerField(default=1, editable=False),
                ),
                (
                    "expires_at",
                    models.DateTimeField(db_index=True, editable=False),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, editable=False),
                ),
            ],
            options={
                "verbose_name": "contador interno de seguridad",
                "verbose_name_plural": "contadores internos de seguridad",
                "db_table": "website_security_rate_limit",
                "default_permissions": (),
            },
        ),
    ]
