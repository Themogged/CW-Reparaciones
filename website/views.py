from __future__ import annotations

import mimetypes
import logging
import json
from pathlib import Path
from xml.sax.saxutils import escape

from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings as django_settings
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .forms import ServiceRequestForm
from .models import (
    BrandVideo,
    CustomerReview,
    CoverageZone,
    FAQItem,
    PortfolioProject,
    Service,
    ServiceCategory,
    ServiceRequest,
    SiteSettings,
)
from .rate_limits import consume_service_request_limit


TRACKING_FIELDS = (
    "source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
)
logger = logging.getLogger(__name__)


def _public_projects():
    return PortfolioProject.objects.filter(
        is_published=True,
        authorization_status=PortfolioProject.AuthorizationStatus.AUTHORIZED,
    ).select_related("service").prefetch_related("videos")


def _public_zones():
    return CoverageZone.objects.filter(is_confirmed=True, is_active=True)


def _public_brand_video():
    return BrandVideo.objects.filter(
        is_published=True,
        authorization_status=BrandVideo.AuthorizationStatus.AUTHORIZED,
    ).first()


def _video_schema(request: HttpRequest, *, video, description: str, upload_date) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": video.title,
        "description": video.description or description,
        "thumbnailUrl": request.build_absolute_uri(video.poster_image.url),
        "uploadDate": upload_date.isoformat(),
        "contentUrl": request.build_absolute_uri(video.full_video.url),
    }
    if video.duration_seconds:
        schema["duration"] = f"PT{video.duration_seconds}S"
    # El texto del administrador no debe poder cerrar el elemento script.
    return (
        json.dumps(schema, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _tracking_initial(request: HttpRequest) -> dict[str, str]:
    return {
        field: request.GET.get(field, "")[:200]
        for field in TRACKING_FIELDS
        if request.GET.get(field)
    }


def _active_services():
    return Service.objects.filter(
        is_active=True, category__is_active=True
    ).select_related("category")


def _service_whatsapp_message(service: Service) -> str:
    messages = {
        "lavadoras": "Hola, vi el servicio de lavadoras de CW Reparaciones y necesito revisar mi lavadora.",
        "neveras": "Hola, vi el servicio de neveras de CW Reparaciones y necesito revisar mi nevera.",
        "aires-acondicionados": "Hola, vi el servicio de aires acondicionados y quisiera solicitar información.",
    }
    if service.slug in messages:
        return messages[service.slug]
    if service.category and service.category.slug == "industriales":
        return "Hola, necesito consultar un servicio técnico para un equipo industrial."
    return f"Hola, vi el servicio de {service.name.lower()} de CW Reparaciones y necesito revisar mi equipo."


def _active_categories():
    return ServiceCategory.objects.filter(is_active=True).prefetch_related(
        Prefetch("services", queryset=_active_services())
    )


def _request_form(request: HttpRequest, **initial) -> ServiceRequestForm:
    values = _tracking_initial(request)
    values.update(initial)
    values.setdefault("source", "website")
    form = ServiceRequestForm(initial=values)
    if not SiteSettings.load().feature_services:
        form.fields["service"].queryset = Service.objects.none()
    return form


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    settings_object = SiteSettings.load()
    if settings_object.feature_services:
        services = _active_services().filter(is_featured=True)
        if not services.exists():
            services = _active_services()
        categories = _active_categories()
    else:
        services = Service.objects.none()
        categories = ServiceCategory.objects.none()

    portfolio_projects = (
        _public_projects()
        if settings_object.feature_portfolio
        else PortfolioProject.objects.none()
    )
    customer_reviews = (
        CustomerReview.objects.filter(is_published=True, is_verified=True)
        if settings_object.feature_reviews
        else CustomerReview.objects.none()
    )
    context = {
        "services": services,
        "service_categories": categories,
        "faqs": FAQItem.objects.filter(is_active=True, service__isnull=True),
        "portfolio_projects": portfolio_projects,
        "brand_video": _public_brand_video(),
        "customer_reviews": customer_reviews,
        "request_form": _request_form(request),
        "coverage_zones": _public_zones(),
        "structured_coverage_zones": _public_zones().filter(
            zone_type__in=(
                CoverageZone.ZoneType.MUNICIPALITY,
                CoverageZone.ZoneType.SECTOR,
            )
        ),
        "contextual_whatsapp_url": settings_object.whatsapp_url_for(
            "Hola, vi la página de CW Reparaciones y necesito solicitar un servicio técnico."
        ),
    }
    return render(request, "website/home.html", context)


@require_GET
def service_list(request: HttpRequest) -> HttpResponse:
    settings_object = SiteSettings.load()
    services = _active_services() if settings_object.feature_services else Service.objects.none()
    categories = (
        _active_categories()
        if settings_object.feature_services
        else ServiceCategory.objects.none()
    )
    return render(
        request,
        "website/services.html",
        {
            "services": services,
            "service_categories": categories,
            "contextual_whatsapp_url": settings_object.whatsapp_url_for(
                "Hola, quisiera consultar un servicio técnico para mi equipo."
            ),
        },
    )


@require_GET
def service_detail(request: HttpRequest, slug: str) -> HttpResponse:
    if not SiteSettings.load().feature_services:
        raise Http404("El catálogo de servicios no está habilitado.")
    service = get_object_or_404(_active_services(), slug=slug)
    faqs = FAQItem.objects.filter(is_active=True).filter(
        Q(service=service) | Q(service__isnull=True)
    )
    return render(
        request,
        "website/service_detail.html",
        {
            "service": service,
            "faqs": faqs,
            "request_form": _request_form(request, service=service),
            "service_projects": _public_projects().filter(service=service),
            "related_services": _active_services().exclude(pk=service.pk)[:4],
            "contextual_whatsapp_url": SiteSettings.load().whatsapp_url_for(
                _service_whatsapp_message(service)
            ),
        },
    )


@require_GET
def service_category(request: HttpRequest, slug: str) -> HttpResponse:
    if not SiteSettings.load().feature_services:
        raise Http404("El catálogo de servicios no está habilitado.")
    category = get_object_or_404(_active_categories(), slug=slug)
    return render(
        request,
        "website/service_category.html",
        {
            "category": category,
            "services": _active_services().filter(category=category),
            "service_categories": _active_categories(),
            "contextual_whatsapp_url": SiteSettings.load().whatsapp_url_for(
                "Hola, necesito consultar un servicio técnico para un equipo industrial."
                if category.slug == "industriales" else
                "Hola, quisiera consultar un servicio técnico para un equipo del hogar."
            ),
        },
    )


@require_GET
def coverage(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "website/coverage.html",
        {
            "coverage_zones": _public_zones(),
            "contextual_whatsapp_url": SiteSettings.load().whatsapp_url_for(
                "Hola, quisiera confirmar si tienen cobertura en mi zona."
            ),
        },
    )


@require_GET
def portfolio_list(request: HttpRequest) -> HttpResponse:
    projects = _public_projects() if SiteSettings.load().feature_portfolio else PortfolioProject.objects.none()
    return render(request, "website/portfolio_list.html", {"portfolio_projects": projects})


@require_GET
def portfolio_detail(request: HttpRequest, slug: str) -> HttpResponse:
    if not SiteSettings.load().feature_portfolio:
        raise Http404("El portafolio no está habilitado.")
    project = get_object_or_404(_public_projects(), slug=slug)
    published_videos = list(project.published_videos)
    video_schemas = []
    for video in published_videos:
        if not video.full_video or not video.poster_image:
            continue
        video_schemas.append(
            _video_schema(
                request,
                video=video,
                description=f"Registro técnico del caso {project.title}.",
                upload_date=video.created_at,
            )
        )
    return render(
        request,
        "website/portfolio_detail.html",
        {
            "project": project,
            "published_videos": published_videos,
            "video_schemas": video_schemas,
            "request_form": _request_form(request, service=project.service) if project.service else _request_form(request),
            "contextual_whatsapp_url": SiteSettings.load().whatsapp_url_for(
                f"Hola, estaba viendo el trabajo técnico de {project.equipment or 'un equipo'}"
                f"{f' {project.brand}' if project.brand else ''} en la página de CW Reparaciones "
                "y necesito revisar un equipo similar."
            ),
        },
    )


@require_GET
def process(request: HttpRequest) -> HttpResponse:
    return render(request, "website/process.html")


@require_GET
def about(request: HttpRequest) -> HttpResponse:
    brand_video = _public_brand_video()
    return render(
        request,
        "website/about.html",
        {
            "brand_video": brand_video,
            "brand_video_schema": (
                _video_schema(
                    request,
                    video=brand_video,
                    description="Presentación audiovisual de CW Reparaciones.",
                    upload_date=brand_video.published_at,
                )
                if brand_video and brand_video.published_at and brand_video.full_video and brand_video.poster_image
                else ""
            ),
        },
    )


@require_GET
def contact(request: HttpRequest) -> HttpResponse:
    settings_object = SiteSettings.load()
    return render(
        request,
        "website/contact.html",
        {
            "request_form": _request_form(request),
            "services": (
                _active_services()
                if settings_object.feature_services
                else Service.objects.none()
            ),
        },
    )


def request_service(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return submit_request(request)
    if request.method != "GET":
        response = HttpResponse(status=405)
        response["Allow"] = "GET, POST"
        return response
    if not SiteSettings.load().feature_diagnostic_form:
        raise Http404("El formulario de solicitudes no está habilitado.")
    return render(
        request,
        "website/request_service.html",
        {
            "request_form": _request_form(request),
            "contextual_whatsapp_url": SiteSettings.load().whatsapp_url_for(
                "Hola, estoy completando una solicitud en la página de CW Reparaciones "
                "y quisiera consultar por WhatsApp."
            ),
        },
    )


def _notify_new_request(service_request: ServiceRequest) -> None:
    if not getattr(django_settings, "WEBSITE_EMAIL_NOTIFICATIONS_ENABLED", False):
        return
    lines = [
        f"Número: {service_request.ticket_number}",
        f"Nombre: {service_request.name}",
        f"WhatsApp: {service_request.whatsapp}",
        f"Teléfono alternativo: {service_request.phone}",
        f"Equipo: {service_request.equipment}",
        f"Marca: {service_request.brand}",
        f"Municipio: {service_request.municipality}",
        f"Sector: {service_request.sector}",
        f"Problema: {service_request.issue}",
        f"Descripción: {service_request.description}",
    ]
    try:
        send_mail(
            f"Nueva solicitud CW Reparaciones — {service_request.ticket_number}",
            "\n".join(lines),
            django_settings.DEFAULT_FROM_EMAIL,
            [django_settings.WEBSITE_CONTACT_TO_EMAIL],
            fail_silently=False,
        )
    except Exception:
        logger.exception("No se pudo enviar la notificación interna de la solicitud %s", service_request.pk)


@require_POST
def submit_request(request: HttpRequest) -> HttpResponse:
    settings_object = SiteSettings.load()
    if not settings_object.feature_diagnostic_form:
        raise Http404("El formulario de solicitudes no está habilitado.")

    # El honeypot recibe una respuesta indistinguible, pero nunca persiste datos.
    if request.POST.get("website"):
        return redirect("website:request_success")

    rate_limit = consume_service_request_limit(request)
    form = ServiceRequestForm(request.POST, request.FILES)
    if not settings_object.feature_services:
        form.fields["service"].queryset = Service.objects.none()
    if rate_limit.limited:
        form.is_valid()
        form.add_error(
            None,
            "Se alcanzó el límite temporal de solicitudes. Inténtalo de nuevo más tarde.",
        )
        response = render(
            request,
            "website/request_service.html",
            {
                "request_form": form,
                "services": (
                    _active_services()
                    if settings_object.feature_services
                    else Service.objects.none()
                ),
            },
            status=429,
        )
        response["Retry-After"] = str(rate_limit.window_seconds)
        return response

    if not form.is_valid():
        return render(
            request,
            "website/request_service.html",
            {
                "request_form": form,
                "services": (
                    _active_services()
                    if settings_object.feature_services
                    else Service.objects.none()
                ),
            },
            status=400,
        )

    service_request = form.save(commit=False)
    if not service_request.source:
        service_request.source = "website"
    service_request.save()
    _notify_new_request(service_request)
    request.session["website_request_submitted"] = service_request.ticket_number
    return redirect("website:request_success")


@require_GET
def request_success(request: HttpRequest) -> HttpResponse:
    ticket_number = request.session.pop("website_request_submitted", None)
    response = render(
        request,
        "website/request_success.html",
        {
            "ticket_number": ticket_number,
            "contextual_whatsapp_url": SiteSettings.load().whatsapp_url_for(
                f"Hola, acabo de enviar la solicitud {ticket_number} desde la página de "
                "CW Reparaciones y quisiera continuar la conversación."
                if ticket_number else
                "Hola, quisiera continuar una consulta con CW Reparaciones por WhatsApp."
            ),
        },
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_GET
def privacy(request: HttpRequest) -> HttpResponse:
    return render(request, "website/privacy.html")


@require_GET
def terms(request: HttpRequest) -> HttpResponse:
    return render(request, "website/terms.html")


@require_GET
def robots(request: HttpRequest) -> HttpResponse:
    sitemap_url = request.build_absolute_uri(reverse("website:sitemap"))
    content = "\n".join(
        (
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /solicitudes/",
            f"Sitemap: {sitemap_url}",
            "",
        )
    )
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


@require_GET
def sitemap(request: HttpRequest) -> HttpResponse:
    settings_object = SiteSettings.load()
    static_names = (
        "home",
        "process",
        "about",
        "contact",
        "privacy",
        "terms",
    )
    if settings_object.feature_services:
        static_names = (*static_names, "service_list")
    if _public_zones().exists():
        static_names = (*static_names, "coverage")
    if settings_object.feature_portfolio and _public_projects().exists():
        static_names = (*static_names, "portfolio_list")
    entries = [
        (request.build_absolute_uri(reverse(f"website:{name}")), None)
        for name in static_names
    ]
    if settings_object.feature_services:
        entries.extend(
            (
                request.build_absolute_uri(service.get_absolute_url()),
                service.updated_at.date().isoformat(),
            )
            for service in _active_services()
        )
    if settings_object.feature_portfolio:
        entries.extend(
            (request.build_absolute_uri(reverse("website:portfolio_detail", args=(project.slug,))), project.updated_at.date().isoformat())
            for project in _public_projects()
        )

    url_nodes = []
    for location, last_modified in entries:
        lastmod_node = f"<lastmod>{last_modified}</lastmod>" if last_modified else ""
        url_nodes.append(f"<url><loc>{escape(location)}</loc>{lastmod_node}</url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(url_nodes)
        + "</urlset>"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@staff_member_required
@require_GET
def request_attachment_download(
    request: HttpRequest, request_id
) -> FileResponse:
    if not (
        request.user.has_perm("website.view_servicerequest")
        or request.user.has_perm("website.change_servicerequest")
    ):
        raise PermissionDenied

    service_request = get_object_or_404(ServiceRequest, pk=request_id)
    if not service_request.diagnostic_media:
        raise Http404("La solicitud no tiene un archivo adjunto.")

    extension = Path(service_request.diagnostic_media.name).suffix.lower()
    content_type = mimetypes.types_map.get(extension, "application/octet-stream")
    try:
        file_handle = service_request.diagnostic_media.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404("El archivo adjunto no está disponible.") from exc

    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=f"solicitud-{service_request.pk}{extension}",
        content_type=content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return response


def error_404(request: HttpRequest, exception) -> HttpResponse:
    return render(request, "website/404.html", status=404)


def error_500(request: HttpRequest) -> HttpResponse:
    return render(request, "website/500.html", status=500)
