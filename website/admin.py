from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from .models import (
    Brand,
    BrandVideo,
    CoverageZone,
    CustomerReview,
    FAQItem,
    PortfolioProject,
    PortfolioVideo,
    Service,
    ServiceCategory,
    ServiceBrand,
    ServiceRequest,
    SiteSettings,
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Marca", {"fields": ("brand_name", "tagline")}),
        (
            "Contacto",
            {
                "fields": (
                    "phone",
                    "whatsapp",
                    "email",
                    "address",
                    "city",
                    "region",
                    "country",
                    "google_maps_url",
                    "google_business_url",
                )
            },
        ),
        ("Redes sociales", {"fields": ("instagram", "facebook", "tiktok", "youtube")}),
        (
            "Horarios",
            {
                "fields": (
                    "hours_monday_friday",
                    "hours_saturday",
                    "hours_sunday",
                    "timezone",
                )
            },
        ),
        (
            "Módulos públicos",
            {
                "fields": (
                    "feature_services",
                    "feature_diagnostic_form",
                    "feature_portfolio",
                    "feature_reviews",
                    "feature_map",
                    "feature_booking",
                    "feature_tracking",
                    "feature_payments",
                    "feature_blog",
                    "feature_client_portal",
                )
            },
        ),
        (
            "SEO y medición",
            {
                "fields": (
                    "default_meta_title",
                    "default_meta_description",
                    "google_analytics_id",
                    "meta_pixel_id",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Datos legales pendientes",
            {
                "fields": (
                    "legal_name", "legal_id", "privacy_email", "data_retention",
                    "media_retention", "media_deletion_policy", "labor_warranty",
                    "parts_warranty", "diagnostic_policy",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request) -> bool:
        return not SiteSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "order", "updated_at")
    list_editable = ("is_active", "order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "short_description")
    ordering = ("order", "name")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "is_featured", "order")
    list_filter = ("category", "is_active", "is_featured")
    list_editable = ("is_active", "is_featured", "order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "short_description", "description")
    autocomplete_fields = ("category",)
    ordering = ("order", "name")


@admin.register(CoverageZone)
class CoverageZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "zone_type", "is_confirmed", "is_active", "order")
    list_filter = ("zone_type", "is_confirmed", "is_active")
    list_editable = ("order",)
    search_fields = ("name", "description")
    ordering = ("order", "name")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ServiceBrand)
class ServiceBrandAdmin(admin.ModelAdmin):
    list_display = ("service", "brand", "supported", "verified", "authorized_service")
    list_filter = ("supported", "verified", "authorized_service", "service")
    search_fields = ("service__name", "brand__name", "notes")
    autocomplete_fields = ("service", "brand")


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ("question", "service", "is_active", "order")
    list_filter = ("is_active", "service")
    list_editable = ("is_active", "order")
    search_fields = ("question", "answer")
    autocomplete_fields = ("service",)
    ordering = ("order", "pk")


@admin.register(PortfolioProject)
class PortfolioProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "service", "authorization_status", "is_published", "completed_on", "order")
    list_filter = ("authorization_status", "is_published", "service")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "equipment", "problem", "work_performed", "result")
    autocomplete_fields = ("service",)
    ordering = ("order", "-completed_on", "title")


@admin.register(PortfolioVideo)
class PortfolioVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "authorization_status", "is_published", "is_featured", "created_at")
    list_filter = ("authorization_status", "is_published", "is_featured")
    search_fields = ("title", "description", "project__title")
    autocomplete_fields = ("project",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BrandVideo)
class BrandVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "authorization_status", "is_published", "published_at")
    list_filter = ("authorization_status", "is_published")
    search_fields = ("title", "description")
    readonly_fields = ("id", "authorized_at", "published_at", "created_at", "updated_at")


@admin.register(CustomerReview)
class CustomerReviewAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "rating",
        "source",
        "is_verified",
        "is_published",
        "order",
    )
    list_filter = ("rating", "is_verified", "is_published", "source")
    list_editable = ("is_verified", "is_published", "order")
    search_fields = ("display_name", "quote", "source")
    ordering = ("order", "-review_date", "pk")


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number",
        "created_at",
        "name",
        "equipment",
        "service",
        "contact_preference",
        "status",
        "has_diagnostic_media",
    )
    list_filter = ("status", "contact_preference", "created_at", "service")
    search_fields = ("ticket_number", "name", "phone", "whatsapp", "email", "equipment", "issue", "municipality")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("service",)
    readonly_fields = (
        "id",
        "ticket_number",
        "created_at",
        "updated_at",
        "service",
        "equipment",
        "brand",
        "model",
        "issue",
        "frequency",
        "description",
        "name",
        "phone",
        "whatsapp",
        "email",
        "municipality", "sector", "address", "preferred_date", "preferred_time",
        "contact_preference",
        "privacy_accepted",
        "consented_at",
        "source",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "attachment_link",
    )
    fieldsets = (
        (
            "Solicitud",
            {
                "fields": (
                    "id",
                    "ticket_number",
                    "created_at",
                    "updated_at",
                    "status",
                    "service",
                    "equipment",
                    "brand", "model",
                    "issue",
                    "frequency",
                    "description",
                    "attachment_link",
                )
            },
        ),
        (
            "Contacto",
            {
                "fields": (
                    "name",
                    "phone",
                    "whatsapp",
                    "email",
                    "municipality", "sector", "address", "preferred_date", "preferred_time",
                    "contact_preference",
                    "privacy_accepted",
                    "consented_at",
                )
            },
        ),
        (
            "Atribución",
            {
                "fields": (
                    "source",
                    "utm_source",
                    "utm_medium",
                    "utm_campaign",
                    "utm_content",
                    "utm_term",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Gestión interna", {"fields": ("internal_notes",)}),
    )

    @admin.display(boolean=True, description="Adjunto")
    def has_diagnostic_media(self, obj: ServiceRequest) -> bool:
        return bool(obj.diagnostic_media)

    @admin.display(description="Archivo privado")
    def attachment_link(self, obj: ServiceRequest):
        if not obj or not obj.diagnostic_media:
            return "Sin archivo adjunto"
        try:
            url = reverse("website:request_attachment_download", args=(obj.pk,))
        except NoReverseMatch:
            return "La ruta privada aún no está conectada al proyecto."
        return format_html('<a href="{}">Descargar archivo adjunto</a>', url)

    def has_add_permission(self, request) -> bool:
        return False
