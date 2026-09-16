from django.db import migrations, models


def unpublish_reviews_without_provenance(apps, schema_editor):
    CustomerReview = apps.get_model("website", "CustomerReview")
    CustomerReview.objects.filter(is_published=True).filter(
        models.Q(is_verified=False) | models.Q(source="")
    ).update(is_published=False)


class Migration(migrations.Migration):
    dependencies = [("website", "0002_seed_confirmed_content")]

    operations = [
        migrations.RunPython(
            unpublish_reviews_without_provenance,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="customerreview",
            constraint=models.CheckConstraint(
                condition=models.Q(is_published=False) | models.Q(is_verified=True),
                name="website_published_review_is_verified",
            ),
        ),
        migrations.AddConstraint(
            model_name="customerreview",
            constraint=models.CheckConstraint(
                condition=models.Q(is_published=False) | ~models.Q(source=""),
                name="website_published_review_has_source",
            ),
        ),
    ]
