from django.apps import AppConfig


class WebsiteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "website"
    verbose_name = "Sitio web"

    def ready(self) -> None:
        from . import checks  # noqa: F401
