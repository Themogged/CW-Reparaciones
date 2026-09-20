from __future__ import annotations

import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote, urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .storage import private_service_request_storage
from .validators import (
    validate_diagnostic_media,
    validate_image_upload,
    validate_private_original_video,
    validate_phone_number,
    validate_public_video,
)


def _unique_slug(instance: models.Model, value: str) -> str:
    base_slug = slugify(value)[:200] or "elemento"
    candidate = base_slug
    suffix = 2
    queryset = type(instance).objects.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    while queryset.filter(slug=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base_slug[: 200 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def private_request_upload_to(instance: "ServiceRequest", filename: str) -> str:
    extension = Path(filename).suffix.lower()
    normalized_extension = ".jpg" if extension == ".jpeg" else extension
    created = instance.created_at if instance.created_at else timezone.now()
    return (
        f"service_requests/{created:%Y/%m}/"
        f"{instance.pk.hex}{normalized_extension}"
    )


def normalize_contact_value(value: str) -> str:
    """Normaliza datos de contacto sin alterar el valor presentado al usuario."""
    normalized = unicodedata.normalize("NFKC", value or "").strip().casefold()
    if "@" in normalized:
        return "".join(normalized.split())
    digits = "".join(character for character in normalized if character.isdigit())
    if len(digits) == 12 and digits.startswith("57"):
        return digits[2:]
    return digits


class SiteSettings(models.Model):
    """Configuración comercial central; solo puede existir el registro con pk=1."""

    brand_name = models.CharField(max_length=120, default="CW Reparaciones")
    tagline = models.CharField(max_length=180, blank=True, default="Servicios Técnicos")

    phone = models.CharField(
        max_length=30,
        blank=True,
        default="+57 317 504 0053",
        validators=[validate_phone_number],
        verbose_name="Teléfono",
    )
    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        default="+57 317 504 0053",
        validators=[validate_phone_number],
        verbose_name="WhatsApp",
    )
    email = models.EmailField(blank=True, default="charlesrodriguez2009@hotmail.com", verbose_name="Correo electrónico")
    address = models.CharField(max_length=240, blank=True, verbose_name="Dirección")
    city = models.CharField(max_length=120, blank=True, verbose_name="Ciudad")
    region = models.CharField(max_length=120, blank=True, verbose_name="Región")
    country = models.CharField(max_length=120, blank=True, default="Colombia", verbose_name="País")
    google_maps_url = models.URLField(blank=True, verbose_name="URL de Google Maps")
    google_business_url = models.URLField(
        blank=True, verbose_name="URL del perfil de Google"
    )

    instagram = models.URLField(blank=True, default="https://www.instagram.com/cwreparaciones/")
    facebook = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)
    youtube = models.URLField(blank=True)

    hours_monday_friday = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Horario de lunes a viernes",
    )
    hours_saturday = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Horario del sábado",
    )
    hours_sunday = models.CharField(
        max_length=80, blank=True, verbose_name="Horario del domingo"
    )
    timezone = models.CharField(
        max_length=64,
        blank=True,
        default="America/Bogota",
        verbose_name="Zona horaria",
    )

    feature_services = models.BooleanField(default=True, verbose_name="Servicios")
    feature_diagnostic_form = models.BooleanField(
        default=True, verbose_name="Formulario de solicitud"
    )
    feature_portfolio = models.BooleanField(default=False, verbose_name="Portafolio")
    feature_reviews = models.BooleanField(default=False, verbose_name="Reseñas")
    feature_map = models.BooleanField(default=False, verbose_name="Mapa")
    feature_booking = models.BooleanField(default=False, verbose_name="Reservas")
    feature_tracking = models.BooleanField(default=False, verbose_name="Seguimiento")
    feature_payments = models.BooleanField(default=False, verbose_name="Pagos")
    feature_blog = models.BooleanField(default=False, verbose_name="Blog")
    feature_client_portal = models.BooleanField(
        default=False, verbose_name="Portal de clientes"
    )

    default_meta_title = models.CharField(max_length=180, blank=True)
    default_meta_description = models.CharField(max_length=320, blank=True)
    google_analytics_id = models.CharField(max_length=40, blank=True)
    meta_pixel_id = models.CharField(max_length=40, blank=True)
    legal_name = models.CharField(max_length=180, blank=True, verbose_name="Nombre legal")
    legal_id = models.CharField(max_length=80, blank=True, verbose_name="NIT o identificación legal")
    privacy_email = models.EmailField(blank=True, verbose_name="Correo de privacidad")
    data_retention = models.CharField(max_length=160, blank=True, verbose_name="Plazo de conservación")
    media_retention = models.CharField(max_length=160, blank=True, verbose_name="Conservación de archivos")
    media_deletion_policy = models.TextField(blank=True, verbose_name="Eliminación de archivos")
    labor_warranty = models.TextField(blank=True, verbose_name="Garantía de mano de obra")
    parts_warranty = models.TextField(blank=True, verbose_name="Garantía de repuestos")
    diagnostic_policy = models.TextField(blank=True, verbose_name="Política de diagnóstico")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración del sitio"
        verbose_name_plural = "configuración del sitio"

    def __str__(self) -> str:
        return self.brand_name

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("La configuración principal no se puede eliminar.")

    @classmethod
    def load(cls) -> "SiteSettings":
        return cls.objects.filter(pk=1).first() or cls(pk=1)

    @property
    def phone_url(self) -> str:
        if not self.phone:
            return ""
        number = "".join(character for character in self.phone if character.isdigit())
        if self.phone.strip().startswith("+"):
            number = f"+{number}"
        return f"tel:{number}" if number else ""

    @property
    def whatsapp_url(self) -> str:
        if not self.whatsapp:
            return ""
        number = "".join(character for character in self.whatsapp if character.isdigit())
        return f"https://wa.me/{number}" if number else ""

    def whatsapp_url_for(self, message: str) -> str:
        base = self.whatsapp_url
        return f"{base}?{urlencode({'text': message})}" if base else ""

    @property
    def email_url(self) -> str:
        return f"mailto:{quote(self.email, safe='@')}" if self.email else ""

    @property
    def display_address(self) -> str:
        return ", ".join(
            part for part in (self.address, self.city, self.region, self.country) if part
        )

    @property
    def has_public_map(self) -> bool:
        return bool(
            self.feature_map and self.google_maps_url and self.display_address
        )


class ServiceCategory(models.Model):
    name = models.CharField(max_length=120, unique=True, verbose_name="Nombre")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    short_description = models.CharField(
        max_length=240, blank=True, verbose_name="Descripción breve"
    )
    icon = models.CharField(
        max_length=80,
        blank=True,
        help_text="Identificador del icono usado por la interfaz.",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    is_active = models.BooleanField(default=True, verbose_name="Visible")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "categoría de servicio"
        verbose_name_plural = "categorías de servicio"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)

    @property
    def description(self) -> str:
        return self.short_description

    @property
    def icon_key(self) -> str:
        return self.icon


class CoverageZone(models.Model):
    class ZoneType(models.TextChoices):
        MUNICIPALITY = "municipality", "Municipio"
        SECTOR = "sector", "Sector"
        AREA = "area", "Área general"
        TO_CONFIRM = "to_confirm", "Zona a consultar"

    name = models.CharField(max_length=120, unique=True, verbose_name="Zona")
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    zone_type = models.CharField(max_length=20, choices=ZoneType.choices)
    description = models.CharField(max_length=240, blank=True)
    is_confirmed = models.BooleanField(default=False, verbose_name="Confirmada")
    is_active = models.BooleanField(default=False, verbose_name="Visible")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "zona de cobertura"
        verbose_name_plural = "zonas de cobertura"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)

    @property
    def whatsapp_url(self) -> str:
        return SiteSettings.load().whatsapp_url_for(
            f"Hola, quisiera confirmar si tienen cobertura en {self.name}."
        )


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "marca de referencia"
        verbose_name_plural = "marcas de referencia"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)


class ServiceBrand(models.Model):
    service = models.ForeignKey("Service", on_delete=models.CASCADE, related_name="brand_links")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="service_links")
    supported = models.BooleanField(default=False, verbose_name="Atendida")
    verified = models.BooleanField(default=False, verbose_name="Verificada")
    authorized_service = models.BooleanField(default=False, verbose_name="Servicio oficial autorizado")
    notes = models.TextField(blank=True, verbose_name="Notas internas")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("service", "brand"), name="website_unique_service_brand")]
        verbose_name = "marca asociada a servicio"
        verbose_name_plural = "marcas asociadas a servicios"

    def __str__(self) -> str:
        return f"{self.service} / {self.brand}"


class Service(models.Model):
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.PROTECT,
        related_name="services",
        verbose_name="Categoría",
    )
    name = models.CharField(max_length=160, verbose_name="Nombre")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    short_description = models.CharField(
        max_length=240, blank=True, verbose_name="Descripción breve"
    )
    icon_key = models.CharField(
        max_length=80,
        blank=True,
        help_text="Identificador del icono usado por la interfaz.",
        verbose_name="Icono",
    )
    description = models.TextField(blank=True, verbose_name="Descripción")
    common_problems = models.TextField(
        blank=True,
        help_text="Un elemento por línea.",
        verbose_name="Problemas frecuentes",
    )
    process = models.TextField(
        blank=True,
        help_text="Describe solo el proceso que pueda confirmarse.",
        verbose_name="Proceso",
    )
    coverage = models.TextField(
        blank=True,
        help_text="No publicar zonas hasta confirmarlas.",
        verbose_name="Cobertura",
    )
    image = models.FileField(
        upload_to="website/services/%Y/%m/",
        blank=True,
        validators=[validate_image_upload],
        verbose_name="Imagen",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    is_featured = models.BooleanField(default=False, verbose_name="Destacado")
    is_active = models.BooleanField(default=True, verbose_name="Visible")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "servicio"
        verbose_name_plural = "servicios"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("website:service_detail", kwargs={"slug": self.slug})

    @property
    def common_problem_list(self) -> list[str]:
        return [line.strip() for line in self.common_problems.splitlines() if line.strip()]

    @property
    def long_description(self) -> str:
        return self.description

    @property
    def problems(self) -> list[str]:
        return self.common_problem_list

    @property
    def process_steps(self) -> list[str]:
        return [line.strip() for line in self.process.splitlines() if line.strip()]

    @property
    def gallery_images(self) -> tuple:
        # Punto de extensión público y seguro hasta incorporar una galería real.
        return ()

    @property
    def verified_brands(self):
        return Brand.objects.filter(
            service_links__service=self,
            service_links__supported=True,
            service_links__verified=True,
        ).distinct()


class FAQItem(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="faq_items",
        blank=True,
        null=True,
        verbose_name="Servicio",
    )
    question = models.CharField(max_length=240, verbose_name="Pregunta")
    answer = models.TextField(verbose_name="Respuesta")
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    is_active = models.BooleanField(default=True, verbose_name="Visible")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "pk")
        verbose_name = "pregunta frecuente"
        verbose_name_plural = "preguntas frecuentes"

    def __str__(self) -> str:
        return self.question


class PortfolioProject(models.Model):
    class AuthorizationStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        AUTHORIZED = "authorized", "Autorizado"
        REJECTED = "rejected", "Rechazado"

    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        related_name="portfolio_projects",
        blank=True,
        null=True,
        verbose_name="Servicio",
    )
    title = models.CharField(max_length=180, verbose_name="Título")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    equipment = models.CharField(max_length=160, blank=True, verbose_name="Equipo")
    brand = models.CharField(max_length=120, blank=True, verbose_name="Marca comprobada")
    model = models.CharField(max_length=120, blank=True, verbose_name="Modelo")
    municipality = models.CharField(max_length=120, blank=True, verbose_name="Municipio")
    sector = models.CharField(max_length=120, blank=True, verbose_name="Sector")
    problem = models.TextField(blank=True, verbose_name="Problema")
    diagnosis = models.TextField(blank=True, verbose_name="Diagnóstico documentado")
    work_performed = models.TextField(blank=True, verbose_name="Trabajo realizado")
    result = models.TextField(blank=True, verbose_name="Resultado verificable")
    completed_on = models.DateField(blank=True, null=True, verbose_name="Fecha")
    before_image = models.FileField(
        upload_to="website/portfolio/before/%Y/%m/",
        blank=True,
        validators=[validate_image_upload],
        verbose_name="Imagen anterior",
    )
    after_image = models.FileField(
        upload_to="website/portfolio/after/%Y/%m/",
        blank=True,
        validators=[validate_image_upload],
        verbose_name="Imagen posterior",
    )
    media = models.FileField(
        upload_to="website/portfolio/media/%Y/%m/",
        blank=True,
        validators=[validate_diagnostic_media],
        verbose_name="Imagen o video adicional",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    is_featured = models.BooleanField(default=False, verbose_name="Destacado")
    authorization_status = models.CharField(
        max_length=20,
        choices=AuthorizationStatus.choices,
        default=AuthorizationStatus.PENDING,
        verbose_name="Autorización de publicación",
    )
    authorized_at = models.DateTimeField(blank=True, null=True)
    authorization_notes = models.TextField(blank=True, verbose_name="Notas privadas de autorización")
    is_published = models.BooleanField(default=False, verbose_name="Publicado")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "-completed_on", "title")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_published=False) | models.Q(authorization_status="authorized"),
                name="website_portfolio_publication_authorized",
            )
        ]
        verbose_name = "trabajo realizado"
        verbose_name_plural = "trabajos realizados"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = _unique_slug(self, self.title)
        if self.authorization_status == self.AuthorizationStatus.AUTHORIZED and self.authorized_at is None:
            self.authorized_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.is_published and self.authorization_status != self.AuthorizationStatus.AUTHORIZED:
            raise ValidationError({"authorization_status": "Confirma la autorización antes de publicar este caso."})

    @property
    def published_videos(self):
        return self.videos.filter(is_published=True, authorization_status="authorized")

    @property
    def solution(self) -> str:
        return self.work_performed


def portfolio_video_upload_to(instance: "PortfolioVideo", filename: str) -> str:
    extension = Path(filename).suffix.lower()
    return f"portfolio_originals/{instance.pk.hex}{extension}"


def portfolio_preview_upload_to(instance: "PortfolioVideo", filename: str) -> str:
    return f"website/portfolio/previews/{instance.pk.hex}.mp4"


def portfolio_full_upload_to(instance: "PortfolioVideo", filename: str) -> str:
    return f"website/portfolio/full/{instance.pk.hex}.mp4"


def portfolio_poster_upload_to(instance: "PortfolioVideo", filename: str) -> str:
    extension = Path(filename).suffix.lower()
    return f"website/portfolio/posters/{instance.pk.hex}{extension}"


class PortfolioVideo(models.Model):
    class AuthorizationStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        AUTHORIZED = "authorized", "Autorizado"
        REJECTED = "rejected", "Rechazado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(PortfolioProject, on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    original_video = models.FileField(
        upload_to=portfolio_video_upload_to,
        storage=private_service_request_storage,
        blank=True,
        validators=[validate_private_original_video],
        verbose_name="Original privado",
    )
    preview_video = models.FileField(
        upload_to=portfolio_preview_upload_to,
        blank=True,
        validators=[validate_public_video],
        verbose_name="Preview web optimizado",
    )
    full_video = models.FileField(
        upload_to=portfolio_full_upload_to,
        blank=True,
        validators=[validate_public_video],
        verbose_name="Video completo web optimizado",
    )
    poster_image = models.FileField(
        upload_to=portfolio_poster_upload_to,
        blank=True,
        validators=[validate_image_upload],
        verbose_name="Poster",
    )
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    width = models.PositiveIntegerField(blank=True, null=True)
    height = models.PositiveIntegerField(blank=True, null=True)
    recorded_on = models.DateField(blank=True, null=True)
    authorization_status = models.CharField(
        max_length=20,
        choices=AuthorizationStatus.choices,
        default=AuthorizationStatus.PENDING,
    )
    authorized_at = models.DateTimeField(blank=True, null=True)
    authorization_notes = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_published=False) | models.Q(authorization_status="authorized"),
                name="website_video_publication_authorized",
            )
        ]
        verbose_name = "video de reparación real"
        verbose_name_plural = "videos de reparaciones reales"

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.is_published and self.authorization_status != self.AuthorizationStatus.AUTHORIZED:
            errors["authorization_status"] = "Confirma la autorización antes de publicar el video."
        if self.is_published and not self.project.is_published:
            errors["project"] = "Publica primero el caso autorizado."
        if self.is_published and not self.preview_video:
            errors["preview_video"] = "Se necesita un preview optimizado para publicación."
        if self.is_published and not self.poster_image:
            errors["poster_image"] = "Se necesita un poster para publicación."
        if self.is_published and not self.full_video:
            errors["full_video"] = "Se necesita un video completo optimizado para publicación."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        if self.authorization_status == self.AuthorizationStatus.AUTHORIZED and self.authorized_at is None:
            self.authorized_at = timezone.now()
        super().save(*args, **kwargs)


def brand_video_upload_to(instance: "BrandVideo", filename: str) -> str:
    return f"brand_video_originals/{instance.pk.hex}{Path(filename).suffix.lower()}"


def brand_preview_upload_to(instance: "BrandVideo", filename: str) -> str:
    return f"website/brand/previews/{instance.pk.hex}.mp4"


def brand_full_upload_to(instance: "BrandVideo", filename: str) -> str:
    return f"website/brand/full/{instance.pk.hex}.mp4"


def brand_poster_upload_to(instance: "BrandVideo", filename: str) -> str:
    return f"website/brand/posters/{instance.pk.hex}{Path(filename).suffix.lower()}"


class BrandVideo(models.Model):
    """Pieza audiovisual de marca; nunca se mezcla con trabajos documentados."""

    class AuthorizationStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        AUTHORIZED = "authorized", "Autorizado"
        REJECTED = "rejected", "Rechazado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    original_video = models.FileField(
        upload_to=brand_video_upload_to,
        storage=private_service_request_storage,
        blank=True,
        validators=[validate_private_original_video],
        verbose_name="Original privado",
    )
    preview_video = models.FileField(
        upload_to=brand_preview_upload_to,
        blank=True,
        validators=[validate_public_video],
        verbose_name="Preview web",
    )
    full_video = models.FileField(
        upload_to=brand_full_upload_to,
        blank=True,
        validators=[validate_public_video],
        verbose_name="Versión web completa",
    )
    poster_image = models.FileField(
        upload_to=brand_poster_upload_to,
        blank=True,
        validators=[validate_image_upload],
        verbose_name="Póster",
    )
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    authorization_status = models.CharField(
        max_length=20,
        choices=AuthorizationStatus.choices,
        default=AuthorizationStatus.PENDING,
    )
    authorized_at = models.DateTimeField(blank=True, null=True)
    authorization_notes = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_published=False) | models.Q(authorization_status="authorized"),
                name="website_brand_video_publication_authorized",
            )
        ]
        verbose_name = "video de marca"
        verbose_name_plural = "videos de marca"

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if not self.is_published:
            return
        errors = {}
        if self.authorization_status != self.AuthorizationStatus.AUTHORIZED:
            errors["authorization_status"] = "Confirma la autorización antes de publicar."
        for field in ("preview_video", "full_video", "poster_image"):
            if not getattr(self, field):
                errors[field] = "Se necesita este derivado web para publicar."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        if self.authorization_status == self.AuthorizationStatus.AUTHORIZED and self.authorized_at is None:
            self.authorized_at = timezone.now()
        if self.is_published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class CustomerReview(models.Model):
    display_name = models.CharField(max_length=120, verbose_name="Nombre público")
    quote = models.TextField(verbose_name="Reseña")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Calificación",
    )
    source = models.CharField(max_length=120, blank=True, verbose_name="Fuente")
    source_url = models.URLField(blank=True, verbose_name="URL de la fuente")
    review_date = models.DateField(blank=True, null=True, verbose_name="Fecha")
    is_verified = models.BooleanField(default=False, verbose_name="Verificada")
    is_published = models.BooleanField(default=False, verbose_name="Publicada")
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "-review_date", "pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="website_review_rating_between_1_and_5",
            ),
            models.CheckConstraint(
                condition=models.Q(is_published=False) | models.Q(is_verified=True),
                name="website_published_review_is_verified",
            ),
            models.CheckConstraint(
                condition=models.Q(is_published=False) | ~models.Q(source=""),
                name="website_published_review_has_source",
            ),
        ]
        verbose_name = "reseña de cliente"
        verbose_name_plural = "reseñas de clientes"

    def __str__(self) -> str:
        return self.display_name

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.is_published and not self.is_verified:
            errors["is_verified"] = "Verifica la reseña antes de publicarla."
        if self.is_published and not self.source.strip():
            errors["source"] = "Indica el origen real antes de publicar la reseña."
        if errors:
            raise ValidationError(errors)

    @property
    def client_name(self) -> str:
        return self.display_name

    @property
    def content(self) -> str:
        return self.quote


class ServiceRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Nueva"
        CONTACTED = "contacted", "Cliente contactado"
        DIAGNOSIS_PENDING = "diagnosis_pending", "Diagnóstico pendiente"
        SCHEDULED = "scheduled", "Programada"
        IN_PROGRESS = "in_progress", "En servicio"
        WAITING_PART = "waiting_part", "Esperando repuesto"
        COMPLETED = "completed", "Finalizada"
        CANCELLED = "cancelled", "Cancelada"

    class Frequency(models.TextChoices):
        CONSTANT = "constant", "Siempre"
        INTERMITTENT = "intermittent", "De forma intermitente"
        FIRST_TIME = "first_time", "Ocurrió una vez"
        UNKNOWN = "unknown", "No estoy seguro"

    class ContactPreference(models.TextChoices):
        PHONE = "phone", "Llamada"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Correo electrónico"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=50, unique=True, blank=True, null=True, editable=False, verbose_name="Número CW")
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        related_name="service_requests",
        blank=True,
        null=True,
        verbose_name="Cliente",
    )
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_service_requests",
        blank=True,
        null=True,
        verbose_name="Técnico asignado",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        related_name="requests",
        blank=True,
        null=True,
        verbose_name="Servicio",
    )
    equipment = models.CharField(max_length=160, verbose_name="Equipo")
    brand = models.CharField(max_length=120, blank=True, verbose_name="Marca")
    model = models.CharField(max_length=120, blank=True, verbose_name="Modelo")
    issue = models.CharField(max_length=160, verbose_name="Problema")
    frequency = models.CharField(
        max_length=20, choices=Frequency.choices, verbose_name="Frecuencia"
    )
    description = models.TextField(max_length=3000, verbose_name="Descripción")
    diagnostic_media = models.FileField(
        upload_to=private_request_upload_to,
        storage=private_service_request_storage,
        validators=[validate_diagnostic_media],
        blank=True,
        verbose_name="Foto o video",
    )

    name = models.CharField(max_length=140, verbose_name="Nombre")
    phone = models.CharField(
        max_length=30, blank=True, validators=[validate_phone_number], verbose_name="Teléfono alternativo"
    )
    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        validators=[validate_phone_number],
        verbose_name="WhatsApp",
    )
    email = models.EmailField(blank=True, verbose_name="Correo electrónico")
    municipality = models.CharField(max_length=120, blank=True, verbose_name="Municipio")
    sector = models.CharField(max_length=120, blank=True, verbose_name="Sector")
    address = models.CharField(max_length=240, blank=True, verbose_name="Dirección particular opcional")
    preferred_date = models.DateField(blank=True, null=True, verbose_name="Fecha preferida (no confirmada)")
    preferred_time = models.TimeField(blank=True, null=True, verbose_name="Hora preferida (no confirmada)")
    contact_preference = models.CharField(
        max_length=20,
        choices=ContactPreference.choices,
        default=ContactPreference.WHATSAPP,
        verbose_name="Preferencia de contacto",
    )
    privacy_accepted = models.BooleanField(
        default=False, verbose_name="Consentimiento de privacidad"
    )
    consented_at = models.DateTimeField(blank=True, null=True)

    source = models.CharField(max_length=200, blank=True)
    utm_source = models.CharField(max_length=200, blank=True)
    utm_medium = models.CharField(max_length=200, blank=True)
    utm_campaign = models.CharField(max_length=200, blank=True)
    utm_content = models.CharField(max_length=200, blank=True)
    utm_term = models.CharField(max_length=200, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    internal_notes = models.TextField(blank=True, verbose_name="Notas internas")
    technical_notes = models.TextField(blank=True, verbose_name="Notas técnicas")
    scheduled_start = models.DateTimeField(blank=True, null=True, verbose_name="Visita programada")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Finalizada el")
    version = models.PositiveIntegerField(default=1, editable=False)
    is_deleted = models.BooleanField(default=False, db_index=True, verbose_name="En papelera")
    deleted_at = models.DateTimeField(blank=True, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(privacy_accepted=True),
                name="website_request_privacy_accepted",
            )
        ]
        indexes = [
            models.Index(fields=("status", "created_at"), name="website_req_status_created"),
            models.Index(fields=("assigned_technician", "status"), name="website_req_tech_status"),
        ]
        permissions = (
            ("assign_servicerequest", "Puede asignar solicitudes a técnicos"),
            ("export_servicerequest", "Puede exportar solicitudes"),
            ("view_all_servicerequest", "Puede ver todas las solicitudes"),
            ("restore_servicerequest", "Puede restaurar solicitudes de la papelera"),
        )
        verbose_name = "solicitud de servicio"
        verbose_name_plural = "solicitudes de servicio"

    def __str__(self) -> str:
        return f"{self.name} — {self.equipment}"

    def clean(self) -> None:
        super().clean()
        errors = {}
        if not self.whatsapp and not self.phone:
            errors["whatsapp"] = "Ingresa al menos un número de contacto."
        if self.contact_preference == self.ContactPreference.WHATSAPP and not self.whatsapp:
            errors["whatsapp"] = "Ingresa un número de WhatsApp para usar este canal."
        if self.contact_preference == self.ContactPreference.EMAIL and not self.email:
            errors["email"] = "Ingresa un correo electrónico para usar este canal."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        creating = self._state.adding
        previous_status = None
        if not creating:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            self.version += 1
        if not self.ticket_number:
            self.ticket_number = TicketSequence.allocate(timezone.localdate().year)
        if self.customer_id is None:
            self.customer = Customer.resolve(
                name=self.name,
                phone=self.phone,
                whatsapp=self.whatsapp,
                email=self.email,
                municipality=self.municipality,
                sector=self.sector,
                address=self.address,
            )
        if self.privacy_accepted and self.consented_at is None:
            self.consented_at = timezone.now()
        if self.status == self.Status.COMPLETED and self.completed_at is None:
            self.completed_at = timezone.now()
        if self.status != self.Status.COMPLETED:
            self.completed_at = None
        super().save(*args, **kwargs)
        if creating:
            ServiceRequestEvent.objects.create(
                service_request=self,
                event_type=ServiceRequestEvent.EventType.CREATED,
                description="Solicitud registrada.",
                metadata={"status": self.status},
            )
        elif previous_status and previous_status != self.status:
            ServiceRequestEvent.objects.create(
                service_request=self,
                event_type=ServiceRequestEvent.EventType.STATUS_CHANGED,
                description=f"Estado actualizado de {previous_status} a {self.status}.",
                metadata={"from": previous_status, "to": self.status},
            )

    def move_to_trash(self) -> None:
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))

    def restore_from_trash(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))


class TicketSequence(models.Model):
    year = models.PositiveSmallIntegerField(primary_key=True)
    next_value = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        verbose_name = "secuencia de ticket"
        verbose_name_plural = "secuencias de tickets"

    @classmethod
    def allocate(cls, year: int) -> str:
        with transaction.atomic():
            sequence, _ = cls.objects.select_for_update().get_or_create(year=year)
            value = sequence.next_value
            sequence.next_value = value + 1
            sequence.save(update_fields=("next_value", "updated_at"))
        return f"CW-{year}-{value:06d}"


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=140, verbose_name="Nombre")
    phone = models.CharField(max_length=30, blank=True, validators=[validate_phone_number], verbose_name="Teléfono")
    whatsapp = models.CharField(max_length=30, blank=True, validators=[validate_phone_number], verbose_name="WhatsApp")
    email = models.EmailField(blank=True, verbose_name="Correo electrónico")
    municipality = models.CharField(max_length=120, blank=True, verbose_name="Municipio")
    sector = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=240, blank=True, verbose_name="Dirección")
    normalized_phone = models.CharField(max_length=80, blank=True, db_index=True, editable=False)
    normalized_whatsapp = models.CharField(max_length=80, blank=True, db_index=True, editable=False)
    normalized_email = models.CharField(max_length=254, blank=True, db_index=True, editable=False)
    duplicate_review_required = models.BooleanField(default=False, db_index=True, verbose_name="Revisar posible duplicado")
    is_deleted = models.BooleanField(default=False, db_index=True, verbose_name="En papelera")
    deleted_at = models.DateTimeField(blank=True, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "created_at")
        indexes = [models.Index(fields=("is_deleted", "created_at"), name="website_customer_active")]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.normalized_phone = normalize_contact_value(self.phone)
        self.normalized_whatsapp = normalize_contact_value(self.whatsapp)
        self.normalized_email = normalize_contact_value(self.email)
        super().save(*args, **kwargs)

    @classmethod
    def resolve(cls, **data) -> "Customer":
        candidates = models.Q()
        has_identifier = False
        for field in ("phone", "whatsapp", "email"):
            value = normalize_contact_value(data.get(field, ""))
            if value:
                has_identifier = True
                candidates |= models.Q(**{f"normalized_{field}": value})
        matches = list(cls.objects.filter(candidates, is_deleted=False)[:2]) if has_identifier else []
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            cls.objects.filter(pk__in=[item.pk for item in matches]).update(duplicate_review_required=True)
        allowed = {"name", "phone", "whatsapp", "email", "municipality", "sector", "address"}
        return cls.objects.create(**{key: value for key, value in data.items() if key in allowed})


class CustomerEquipment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="equipment")
    equipment_type = models.CharField(max_length=160, verbose_name="Equipo")
    brand = models.CharField(max_length=120, blank=True, verbose_name="Marca")
    model = models.CharField(max_length=120, blank=True, verbose_name="Modelo")
    serial_number = models.CharField(max_length=120, blank=True, verbose_name="Serie")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("equipment_type", "brand", "model")
        verbose_name = "equipo del cliente"
        verbose_name_plural = "equipos del cliente"

    def __str__(self) -> str:
        return f"{self.equipment_type} {self.brand} {self.model}".strip()


class ServiceRequestNote(models.Model):
    class Visibility(models.TextChoices):
        INTERNAL = "internal", "Interna"
        TECHNICAL = "technical", "Técnica"

    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="service_request_notes")
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.INTERNAL)
    body = models.TextField(max_length=5000, verbose_name="Nota")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "nota de solicitud"
        verbose_name_plural = "notas de solicitud"


class ServiceRequestEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Creación"
        STATUS_CHANGED = "status_changed", "Cambio de estado"
        ASSIGNED = "assigned", "Asignación"
        NOTE_ADDED = "note_added", "Nota agregada"
        EXPORTED = "exported", "Exportación"
        RESTORED = "restored", "Restauración"

    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="timeline")
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="service_request_events")
    description = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        default_permissions = ("view",)
        verbose_name = "evento de solicitud"
        verbose_name_plural = "timeline de solicitudes"


class UserProfile(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrador"
        TECHNICIAN = "technician", "Técnico"
        CONTENT_MANAGER = "content_manager", "Gestor de contenido"
        VIEWER = "viewer", "Solo lectura"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cw_profile")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.VIEWER, db_index=True)
    phone = models.CharField(max_length=30, blank=True, validators=[validate_phone_number])
    timezone = models.CharField(max_length=64, default="America/Bogota")
    must_change_password = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuarios"


class SavedFilter(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_filters")
    name = models.CharField(max_length=100)
    target = models.CharField(max_length=100, default="service_requests")
    filters = models.JSONField(default=dict)
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("owner", "target", "name"), name="website_unique_saved_filter")]
        ordering = ("name",)
        verbose_name = "filtro guardado"
        verbose_name_plural = "filtros guardados"


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Creación"
        UPDATE = "update", "Actualización"
        DELETE = "delete", "Envío a papelera"
        RESTORE = "restore", "Restauración"
        EXPORT = "export", "Exportación"
        LOGIN = "login", "Inicio de sesión"
        LOGIN_FAILED = "login_failed", "Inicio de sesión fallido"
        LOGOUT = "logout", "Cierre de sesión"
        BACKUP = "backup", "Respaldo"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events")
    action = models.CharField(max_length=24, choices=Action.choices, db_index=True)
    object_type = models.CharField(max_length=120, db_index=True)
    object_id = models.CharField(max_length=120, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    request_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        default_permissions = ("view",)
        verbose_name = "evento de auditoría"
        verbose_name_plural = "auditoría"

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            raise ValidationError("Los eventos de auditoría son inmutables.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los eventos de auditoría no se pueden eliminar.")


class LoginEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_events",
    )
    username = models.CharField(max_length=150, blank=True)
    success = models.BooleanField(db_index=True)
    event = models.CharField(max_length=16, default="login")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        default_permissions = ("view",)
        verbose_name = "evento de acceso"
        verbose_name_plural = "historial de accesos"


class ExportRecord(models.Model):
    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "Excel"
        PDF = "pdf", "PDF"
        JSON = "json", "JSON"

    class Status(models.TextChoices):
        PROCESSING = "processing", "Procesando"
        READY = "ready", "Disponible"
        FAILED = "failed", "Fallida"
        EXPIRED = "expired", "Expirada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="exports")
    export_type = models.CharField(max_length=60, default="service_requests")
    file_format = models.CharField(max_length=8, choices=Format.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING, db_index=True)
    parameters = models.JSONField(default=dict, blank=True)
    relative_path = models.CharField(max_length=500, blank=True, editable=False)
    original_filename = models.CharField(max_length=255, blank=True, editable=False)
    row_count = models.PositiveIntegerField(default=0, editable=False)
    size_bytes = models.PositiveBigIntegerField(default=0, editable=False)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)
    error_message = models.CharField(max_length=500, blank=True, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        permissions = (("download_exportrecord", "Puede descargar exportaciones"),)
        verbose_name = "exportación"
        verbose_name_plural = "historial de exportaciones"


class BackupRecord(models.Model):
    class Scope(models.TextChoices):
        DATABASE = "database", "Base de datos"
        MEDIA = "media", "Archivos multimedia"
        FULL = "full", "Completo"

    class Status(models.TextChoices):
        PROCESSING = "processing", "Procesando"
        READY = "ready", "Disponible"
        FAILED = "failed", "Fallido"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="backups")
    scope = models.CharField(max_length=16, choices=Scope.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    relative_path = models.CharField(max_length=500, blank=True, editable=False)
    size_bytes = models.PositiveBigIntegerField(default=0, editable=False)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)
    error_message = models.CharField(max_length=500, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        permissions = (
            ("create_backuprecord", "Puede crear respaldos"),
            ("restore_backuprecord", "Puede restaurar respaldos"),
        )
        verbose_name = "respaldo"
        verbose_name_plural = "respaldos"


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=140)
    is_closed = models.BooleanField(default=True)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("date",)
        verbose_name = "festivo o excepción"
        verbose_name_plural = "festivos y excepciones"


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "método de pago"
        verbose_name_plural = "métodos de pago"


class RedirectRule(models.Model):
    source_path = models.CharField(max_length=255, unique=True)
    destination_url = models.CharField(max_length=500)
    is_permanent = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "redirección"
        verbose_name_plural = "redirecciones"

    def clean(self) -> None:
        if not self.source_path.startswith("/"):
            raise ValidationError({"source_path": "La ruta debe comenzar con /."})


class PrivacyRequest(models.Model):
    class RequestType(models.TextChoices):
        ACCESS = "access", "Acceso"
        CORRECTION = "correction", "Corrección"
        DELETION = "deletion", "Eliminación"

    class Status(models.TextChoices):
        RECEIVED = "received", "Recibida"
        VERIFYING = "verifying", "Verificando identidad"
        PROCESSING = "processing", "En proceso"
        COMPLETED = "completed", "Completada"
        REJECTED = "rejected", "Rechazada"

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="privacy_requests")
    request_type = models.CharField(max_length=16, choices=RequestType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    requester_name = models.CharField(max_length=140)
    requester_contact = models.CharField(max_length=254)
    verified_at = models.DateTimeField(blank=True, null=True)
    due_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "solicitud de privacidad"
        verbose_name_plural = "solicitudes de privacidad"


class SecurityRateLimitBucket(models.Model):
    """Contador seudonimizado y compartido entre procesos para frenar abuso."""

    key = models.CharField(max_length=64, primary_key=True, editable=False)
    scope = models.CharField(max_length=48, db_index=True, editable=False)
    count = models.PositiveIntegerField(default=1, editable=False)
    expires_at = models.DateTimeField(db_index=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        db_table = "website_security_rate_limit"
        default_permissions = ()
        verbose_name = "contador interno de seguridad"
        verbose_name_plural = "contadores internos de seguridad"
