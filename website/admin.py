from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from .business.exports import create_service_request_export
from .models import (
    AuditEvent,
    BackupRecord,
    Brand,
    BrandVideo,
    CoverageZone,
    Customer,
    CustomerEquipment,
    CustomerReview,
    ExportRecord,
    FAQItem,
    Holiday,
    LoginEvent,
    PaymentMethod,
    PortfolioProject,
    PortfolioVideo,
    PrivacyRequest,
    RedirectRule,
    SavedFilter,
    Service,
    ServiceCategory,
    ServiceBrand,
    ServiceRequest,
    ServiceRequestEvent,
    ServiceRequestNote,
    SiteSettings,
    UserProfile,
)


admin.site.site_header = "CW Reparaciones · Centro de Control"
admin.site.site_title = "Administración CW"
admin.site.index_title = "Resumen del negocio"
admin.site.index_template = "admin/cw_index.html"


def _request_ip(request):
    return request.META.get("REMOTE_ADDR") or None


class AuditAdminMixin:
    """Audita mutaciones administrativas sin almacenar contraseñas ni archivos."""

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action=AuditEvent.Action.UPDATE if change else AuditEvent.Action.CREATE,
            object_type=obj._meta.label_lower,
            object_id=str(obj.pk),
            object_repr=str(obj)[:255],
            changes={"fields": list(form.changed_data)},
            ip_address=_request_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )

    def delete_model(self, request, obj):
        object_type = obj._meta.label_lower
        object_id = str(obj.pk)
        object_repr = str(obj)[:255]
        super().delete_model(request, obj)
        AuditEvent.objects.create(
            actor=request.user,
            action=AuditEvent.Action.DELETE,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr,
            ip_address=_request_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )


class ServiceRequestAdminForm(forms.ModelForm):
    MANUAL_CHANNEL_CHOICES = (
        ("phone", "Llamada telefónica"),
        ("whatsapp", "WhatsApp"),
        ("in_person", "Atención presencial"),
        ("email", "Correo electrónico"),
        ("referral", "Recomendación"),
        ("other", "Otro medio"),
    )

    version_token = forms.IntegerField(widget=forms.HiddenInput)
    manual_channel = forms.ChoiceField(
        label="¿Cómo llegó la solicitud?",
        choices=MANUAL_CHANNEL_CHOICES,
        required=False,
        help_text="Selecciona el medio por el que el cliente pidió el servicio.",
    )

    class Meta:
        model = ServiceRequest
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["version_token"].initial = self.instance.version
        if self.instance._state.adding:
            self.fields["manual_channel"].required = True
            self.fields["privacy_accepted"].required = True
            self.fields["privacy_accepted"].label = (
                "Confirmo que el cliente autorizó registrar sus datos"
            )
            self.fields["privacy_accepted"].help_text = (
                "Márcalo solo después de recibir la autorización del cliente "
                "por llamada, WhatsApp, correo o de forma presencial."
            )

    def clean(self):
        cleaned = super().clean()
        if not self.instance._state.adding:
            stored_version = ServiceRequest.objects.filter(pk=self.instance.pk).values_list("version", flat=True).first()
            if stored_version != cleaned.get("version_token"):
                raise ValidationError(
                    "Esta solicitud fue modificada por otra persona. Recarga la página antes de guardar."
                )
        return cleaned


@admin.register(SiteSettings)
class SiteSettingsAdmin(AuditAdminMixin, admin.ModelAdmin):
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
class ServiceCategoryAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "is_active", "order", "updated_at")
    list_editable = ("is_active", "order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "short_description")
    ordering = ("order", "name")


@admin.register(Service)
class ServiceAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "is_featured", "order")
    list_filter = ("category", "is_active", "is_featured")
    list_editable = ("is_active", "is_featured", "order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "short_description", "description")
    autocomplete_fields = ("category",)
    ordering = ("order", "name")


@admin.register(CoverageZone)
class CoverageZoneAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "zone_type", "is_confirmed", "is_active", "order")
    list_filter = ("zone_type", "is_confirmed", "is_active")
    list_editable = ("order",)
    search_fields = ("name", "description")
    ordering = ("order", "name")


@admin.register(Brand)
class BrandAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ServiceBrand)
class ServiceBrandAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("service", "brand", "supported", "verified", "authorized_service")
    list_filter = ("supported", "verified", "authorized_service", "service")
    search_fields = ("service__name", "brand__name", "notes")
    autocomplete_fields = ("service", "brand")


@admin.register(FAQItem)
class FAQItemAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("question", "service", "is_active", "order")
    list_filter = ("is_active", "service")
    list_editable = ("is_active", "order")
    search_fields = ("question", "answer")
    autocomplete_fields = ("service",)
    ordering = ("order", "pk")


@admin.register(PortfolioProject)
class PortfolioProjectAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("title", "service", "authorization_status", "is_published", "completed_on", "order")
    list_filter = ("authorization_status", "is_published", "service")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "equipment", "problem", "work_performed", "result")
    autocomplete_fields = ("service",)
    ordering = ("order", "-completed_on", "title")


@admin.register(PortfolioVideo)
class PortfolioVideoAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("title", "project", "authorization_status", "is_published", "is_featured", "created_at")
    list_filter = ("authorization_status", "is_published", "is_featured")
    search_fields = ("title", "description", "project__title")
    autocomplete_fields = ("project",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BrandVideo)
class BrandVideoAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("title", "authorization_status", "is_published", "published_at")
    list_filter = ("authorization_status", "is_published")
    search_fields = ("title", "description")
    readonly_fields = ("id", "authorized_at", "published_at", "created_at", "updated_at")


@admin.register(CustomerReview)
class CustomerReviewAdmin(AuditAdminMixin, admin.ModelAdmin):
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


class ServiceRequestNoteInline(admin.TabularInline):
    model = ServiceRequestNote
    extra = 0
    fields = ("visibility", "body", "author", "created_at")
    readonly_fields = ("author", "created_at")
    ordering = ("-created_at",)


class ServiceRequestEventInline(admin.TabularInline):
    model = ServiceRequestEvent
    extra = 0
    fields = ("created_at", "event_type", "actor", "description")
    readonly_fields = fields
    ordering = ("-created_at",)
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(AuditAdminMixin, admin.ModelAdmin):
    form = ServiceRequestAdminForm
    change_list_template = "admin/website/servicerequest/change_list.html"
    list_display = (
        "ticket_number",
        "created_at",
        "name",
        "equipment",
        "service",
        "status",
        "assigned_technician",
        "municipality",
        "has_diagnostic_media",
    )
    list_filter = ("status", "assigned_technician", "contact_preference", "created_at", "service", "municipality", "source", "is_deleted")
    search_fields = (
        "ticket_number", "name", "phone", "whatsapp", "email", "equipment",
        "brand", "model", "issue", "municipality", "sector", "description",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("service", "customer", "assigned_technician")
    list_select_related = ("service", "customer", "assigned_technician")
    list_per_page = 40
    save_on_top = True
    inlines = (ServiceRequestNoteInline, ServiceRequestEventInline)
    actions = (
        "export_csv",
        "export_xlsx",
        "export_pdf",
        "export_json",
        "move_selected_to_trash",
        "restore_selected",
    )
    readonly_fields = (
        "id",
        "ticket_number",
        "created_at",
        "updated_at",
        "completed_at",
        "deleted_at",
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
        "customer_link",
        "whatsapp_link",
        "service_order_links",
    )
    fieldsets = (
        (
            "Solicitud",
            {
                "fields": (
                    "id",
                    "version_token",
                    "ticket_number",
                    "created_at",
                    "updated_at",
                    "status",
                    "assigned_technician",
                    "scheduled_start",
                    "completed_at",
                    "service",
                    "equipment",
                    "brand", "model",
                    "issue",
                    "frequency",
                    "description",
                    "attachment_link",
                    "service_order_links",
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
                    "customer_link",
                    "whatsapp_link",
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
        ("Gestión interna", {"fields": ("technical_notes", "internal_notes", "is_deleted", "deleted_at")}),
    )
    add_fieldsets = (
        (
            "Registro manual",
            {
                "description": (
                    "Usa este formulario cuando el cliente pidió el servicio por llamada, "
                    "WhatsApp, correo o de forma presencial. El número CW se genera al guardar."
                ),
                "fields": (
                    "version_token",
                    "manual_channel",
                    "status",
                    "assigned_technician",
                    "scheduled_start",
                ),
            },
        ),
        (
            "Equipo y problema",
            {
                "fields": (
                    "service",
                    "equipment",
                    "brand",
                    "model",
                    "issue",
                    "frequency",
                    "description",
                    "diagnostic_media",
                )
            },
        ),
        (
            "Datos del cliente",
            {
                "fields": (
                    "name",
                    "phone",
                    "whatsapp",
                    "email",
                    "municipality",
                    "sector",
                    "address",
                    "preferred_date",
                    "preferred_time",
                    "contact_preference",
                    "privacy_accepted",
                )
            },
        ),
        (
            "Información interna opcional",
            {"fields": ("technical_notes", "internal_notes")},
        ),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    @admin.display(boolean=True, description="Adjunto")
    def has_diagnostic_media(self, obj: ServiceRequest) -> bool:
        return bool(obj.diagnostic_media)

    @admin.display(description="Archivo privado")
    def attachment_link(self, obj: ServiceRequest):
        if not obj or not obj.diagnostic_media:
            return "Sin archivo adjunto"
        if obj.is_deleted:
            return "Restaura la solicitud para acceder al archivo."
        try:
            url = reverse("website:request_attachment_download", args=(obj.pk,))
        except NoReverseMatch:
            return "La ruta privada aún no está conectada al proyecto."
        return format_html('<a href="{}">Descargar archivo adjunto</a>', url)

    @admin.display(description="Cliente CRM")
    def customer_link(self, obj: ServiceRequest):
        if not obj or not obj.customer_id:
            return "Sin ficha vinculada"
        url = reverse("admin:website_customer_change", args=(obj.customer_id,))
        return format_html('<a href="{}">Abrir ficha de {}</a>', url, obj.customer.name)

    @admin.display(description="WhatsApp")
    def whatsapp_link(self, obj: ServiceRequest):
        if not obj or not obj.whatsapp:
            return "Sin WhatsApp"
        digits = "".join(character for character in obj.whatsapp if character.isdigit())
        message = f"Hola {obj.name}, te contactamos de CW Reparaciones sobre la solicitud {obj.ticket_number}."
        from urllib.parse import quote
        return format_html(
            '<a class="button" href="https://wa.me/{}?text={}" target="_blank" rel="noopener">Abrir conversación</a>',
            digits,
            quote(message),
        )

    @admin.display(description="Documentos")
    def service_order_links(self, obj: ServiceRequest):
        if not obj or not obj.pk:
            return "Disponible al guardar"
        if obj.is_deleted:
            return "Restaura la solicitud para generar documentos."
        url = reverse("website:service_order_pdf", args=(obj.pk,))
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Orden cliente</a> · '
            '<a href="{}?mode=internal" target="_blank" rel="noopener">Orden interna</a>',
            url,
            url,
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        profile = getattr(request.user, "cw_profile", None)
        if profile and profile.role == UserProfile.Role.TECHNICIAN:
            return queryset.filter(assigned_technician=request.user)
        return queryset

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        profile = getattr(request.user, "cw_profile", None)
        if allowed and obj and profile and profile.role == UserProfile.Role.TECHNICIAN:
            return obj.assigned_technician_id == request.user.pk
        return allowed

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        readonly = list(super().get_readonly_fields(request, obj))
        profile = getattr(request.user, "cw_profile", None)
        if profile and profile.role == UserProfile.Role.TECHNICIAN:
            readonly.extend(("assigned_technician", "scheduled_start", "internal_notes", "is_deleted", "deleted_at"))
        return tuple(dict.fromkeys(readonly))

    def save_model(self, request, obj, form, change):
        previous_assignee = None
        if change:
            previous_assignee = ServiceRequest.objects.filter(pk=obj.pk).values_list("assigned_technician_id", flat=True).first()
        else:
            obj.source = f"manual:{form.cleaned_data['manual_channel']}"
        super().save_model(request, obj, form, change)
        if not change:
            channel_label = dict(ServiceRequestAdminForm.MANUAL_CHANNEL_CHOICES).get(
                form.cleaned_data["manual_channel"],
                form.cleaned_data["manual_channel"],
            )
            ServiceRequestEvent.objects.filter(
                service_request=obj,
                event_type=ServiceRequestEvent.EventType.CREATED,
                actor__isnull=True,
            ).update(
                actor=request.user,
                description=f"Solicitud manual registrada desde {channel_label.lower()}.",
                metadata={"status": obj.status, "source": obj.source},
            )
        if previous_assignee != obj.assigned_technician_id:
            ServiceRequestEvent.objects.create(
                service_request=obj,
                event_type=ServiceRequestEvent.EventType.ASSIGNED,
                actor=request.user,
                description=(
                    f"Solicitud asignada a {obj.assigned_technician.get_username()}."
                    if obj.assigned_technician else "Asignación retirada."
                ),
            )

    def add_view(self, request, form_url="", extra_context=None):
        context = {
            "title": "Nueva solicitud manual",
            "subtitle": "Registra un servicio solicitado fuera del formulario web.",
        }
        if extra_context:
            context.update(extra_context)
        return super().add_view(request, form_url, context)

    def response_add(self, request, obj, post_url_continue=None):
        if "_addanother" in request.POST:
            return super().response_add(request, obj, post_url_continue)
        self.message_user(
            request,
            (
                f"Solicitud manual {obj.ticket_number} creada correctamente. "
                "Ya puedes abrir la orden para cliente o la orden interna."
            ),
            messages.SUCCESS,
        )
        return HttpResponseRedirect(
            reverse("admin:website_servicerequest_change", args=(obj.pk,))
        )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, ServiceRequestNote) and not instance.author_id:
                instance.author = request.user
                instance.save()
                ServiceRequestEvent.objects.create(
                    service_request=instance.service_request,
                    event_type=ServiceRequestEvent.EventType.NOTE_ADDED,
                    actor=request.user,
                    description=f"Nota {instance.get_visibility_display().lower()} agregada.",
                )
            else:
                instance.save()
        for deleted in formset.deleted_objects:
            deleted.delete()
        formset.save_m2m()

    def has_export_permission(self, request):
        return request.user.has_perm("website.export_servicerequest")

    def _export(self, request, queryset, file_format):
        if not self.has_export_permission(request):
            raise PermissionDenied
        record = create_service_request_export(
            user=request.user,
            queryset=queryset,
            file_format=file_format,
            parameters={"selection": "selected", "count": queryset.count()},
        )
        url = reverse("website:export_download", args=(record.token,))
        self.message_user(
            request,
            format_html('Exportación lista: <a href="{}">descargar {}</a>. Caduca el {}.', url, record.get_file_format_display(), record.expires_at.strftime("%d/%m/%Y %H:%M")),
            messages.SUCCESS,
        )

    @admin.action(description="Exportar seleccionados a CSV", permissions=("export",))
    def export_csv(self, request, queryset):
        self._export(request, queryset, ExportRecord.Format.CSV)

    @admin.action(description="Exportar seleccionados a Excel", permissions=("export",))
    def export_xlsx(self, request, queryset):
        self._export(request, queryset, ExportRecord.Format.XLSX)

    @admin.action(description="Exportar seleccionados a PDF corporativo", permissions=("export",))
    def export_pdf(self, request, queryset):
        self._export(request, queryset, ExportRecord.Format.PDF)

    @admin.action(description="Exportar seleccionados a JSON", permissions=("export",))
    def export_json(self, request, queryset):
        self._export(request, queryset, ExportRecord.Format.JSON)

    @admin.action(description="Mover seleccionados a la papelera", permissions=("delete",))
    def move_selected_to_trash(self, request, queryset):
        count = 0
        for item in queryset.filter(is_deleted=False):
            item.move_to_trash()
            count += 1
        self.message_user(request, f"{count} solicitudes movidas a la papelera.")

    @admin.action(description="Restaurar seleccionados")
    def restore_selected(self, request, queryset):
        if not request.user.has_perm("website.restore_servicerequest"):
            raise PermissionDenied
        count = 0
        for item in queryset.filter(is_deleted=True):
            item.restore_from_trash()
            ServiceRequestEvent.objects.create(
                service_request=item,
                event_type=ServiceRequestEvent.EventType.RESTORED,
                actor=request.user,
                description="Solicitud restaurada desde la papelera.",
            )
            count += 1
        self.message_user(request, f"{count} solicitudes restauradas.")

    def delete_model(self, request, obj):
        obj.move_to_trash()
        AuditEvent.objects.create(
            actor=request.user,
            action=AuditEvent.Action.DELETE,
            object_type=obj._meta.label_lower,
            object_id=str(obj.pk),
            object_repr=str(obj)[:255],
            changes={"soft_delete": True},
            ip_address=_request_ip(request),
        )

    def delete_queryset(self, request, queryset):
        for item in queryset:
            self.delete_model(request, item)

    def has_add_permission(self, request) -> bool:
        return super().has_add_permission(request)


class CustomerEquipmentInline(admin.TabularInline):
    model = CustomerEquipment
    extra = 0


class CustomerRequestInline(admin.TabularInline):
    model = ServiceRequest
    fields = ("ticket_number", "created_at", "equipment", "status", "assigned_technician")
    readonly_fields = fields
    extra = 0
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Customer)
class CustomerAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "whatsapp", "email", "municipality", "request_count", "duplicate_review_required", "updated_at")
    list_filter = ("duplicate_review_required", "is_deleted", "municipality", "created_at")
    search_fields = ("name", "phone", "whatsapp", "email", "municipality", "sector")
    readonly_fields = ("normalized_phone", "normalized_whatsapp", "normalized_email", "created_at", "updated_at", "deleted_at")
    inlines = (CustomerEquipmentInline, CustomerRequestInline)
    list_per_page = 40

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_request_count=Count("service_requests"))

    @admin.display(description="Solicitudes", ordering="_request_count")
    def request_count(self, obj):
        return obj._request_count


@admin.register(ServiceRequestNote)
class ServiceRequestNoteAdmin(admin.ModelAdmin):
    list_display = ("service_request", "visibility", "author", "created_at")
    list_filter = ("visibility", "created_at")
    search_fields = ("service_request__ticket_number", "body", "author__username")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("service_request", "author")


@admin.register(ServiceRequestEvent)
class ServiceRequestEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "service_request", "event_type", "actor", "description")
    list_filter = ("event_type", "created_at")
    search_fields = ("service_request__ticket_number", "description", "actor__username")
    readonly_fields = ("service_request", "event_type", "actor", "description", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExportRecord)
class ExportRecordAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "file_format", "created_by", "created_at", "row_count", "status", "formatted_size", "download_link")
    list_filter = ("file_format", "status", "created_at", "created_by")
    search_fields = ("original_filename", "created_by__username", "sha256")
    readonly_fields = tuple(field.name for field in ExportRecord._meta.fields)

    @admin.display(description="Tamaño")
    def formatted_size(self, obj):
        return f"{obj.size_bytes / 1024:.1f} KB" if obj.size_bytes else "—"

    @admin.display(description="Archivo")
    def download_link(self, obj):
        if obj.status != ExportRecord.Status.READY:
            return "No disponible"
        return format_html('<a href="{}">Descargar</a>', reverse("website:export_download", args=(obj.token,)))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "object_repr", "ip_address")
    list_filter = ("action", "object_type", "created_at", "actor")
    search_fields = ("object_repr", "object_id", "actor__username", "request_id")
    readonly_fields = tuple(field.name for field in AuditEvent._meta.fields)
    list_per_page = 60

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "username", "event", "success", "ip_address")
    list_filter = ("success", "event", "created_at")
    search_fields = ("username", "ip_address", "user_agent")
    readonly_fields = tuple(field.name for field in LoginEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "scope", "created_by", "status", "size_bytes", "sha256")
    list_filter = ("scope", "status", "created_at")
    readonly_fields = tuple(field.name for field in BackupRecord._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("user", "role", "phone", "timezone", "updated_at")
    list_filter = ("role", "timezone")
    search_fields = ("user__username", "user__first_name", "user__last_name", "user__email", "phone")
    autocomplete_fields = ("user",)


@admin.register(SavedFilter)
class SavedFilterAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "target", "is_shared", "created_at")
    list_filter = ("target", "is_shared")
    search_fields = ("name", "owner__username")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser or getattr(getattr(request.user, "cw_profile", None), "role", "") in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            return queryset
        return queryset.filter(owner=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


for model in (Holiday, PaymentMethod, RedirectRule, PrivacyRequest):
    admin.site.register(model)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0


class CWUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = (*UserAdmin.list_display, "cw_role")

    @admin.display(description="Rol CW")
    def cw_role(self, obj):
        profile = getattr(obj, "cw_profile", None)
        return profile.get_role_display() if profile else "Sin perfil"

    def save_model(self, request, obj, form, change):
        if change and not obj.is_active:
            profile = getattr(obj, "cw_profile", None)
            if profile and profile.role == UserProfile.Role.OWNER:
                other_owners = UserProfile.objects.filter(role=UserProfile.Role.OWNER, user__is_active=True).exclude(user=obj)
                if not other_owners.exists():
                    raise ValidationError("No se puede desactivar al último OWNER activo.")
        super().save_model(request, obj, form, change)


User = get_user_model()
admin.site.unregister(User)
admin.site.register(User, CWUserAdmin)
