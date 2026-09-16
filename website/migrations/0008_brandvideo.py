import uuid

import website.models
import website.storage
import website.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0007_alter_servicerequest_contact_preference"),
    ]

    operations = [
        migrations.CreateModel(
            name="BrandVideo",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("original_video", models.FileField(blank=True, storage=website.storage.PrivateServiceRequestStorage(), upload_to=website.models.brand_video_upload_to, validators=[website.validators.validate_private_original_video], verbose_name="Original privado")),
                ("preview_video", models.FileField(blank=True, upload_to=website.models.brand_preview_upload_to, validators=[website.validators.validate_public_video], verbose_name="Preview web")),
                ("full_video", models.FileField(blank=True, upload_to=website.models.brand_full_upload_to, validators=[website.validators.validate_public_video], verbose_name="Versión web completa")),
                ("poster_image", models.FileField(blank=True, upload_to=website.models.brand_poster_upload_to, validators=[website.validators.validate_image_upload], verbose_name="Póster")),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("authorization_status", models.CharField(choices=[("pending", "Pendiente"), ("authorized", "Autorizado"), ("rejected", "Rechazado")], default="pending", max_length=20)),
                ("authorized_at", models.DateTimeField(blank=True, null=True)),
                ("authorization_notes", models.TextField(blank=True)),
                ("is_published", models.BooleanField(default=False)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "video de marca",
                "verbose_name_plural": "videos de marca",
                "ordering": ("-created_at",),
                "constraints": [models.CheckConstraint(condition=models.Q(is_published=False) | models.Q(authorization_status="authorized"), name="website_brand_video_publication_authorized")],
            },
        ),
    ]
