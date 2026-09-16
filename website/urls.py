from django.urls import path, re_path

from . import views


app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("servicios/", views.service_list, name="service_list"),
    re_path(r"^servicios/(?P<slug>hogar|industriales)/$", views.service_category, name="service_category"),
    path("servicios/<slug:slug>/", views.service_detail, name="service_detail"),
    path("cobertura/", views.coverage, name="coverage"),
    path("trabajos/", views.portfolio_list, name="portfolio_list"),
    path("trabajos/<slug:slug>/", views.portfolio_detail, name="portfolio_detail"),
    path("como-trabajamos/", views.process, name="process"),
    path("nosotros/", views.about, name="about"),
    path("contacto/", views.contact, name="contact"),
    path("solicitar-servicio/", views.request_service, name="request_service"),
    path("solicitar-servicio/", views.request_service, name="submit_request"),
    path("solicitud-enviada/", views.request_success, name="request_success"),
    path("privacidad/", views.privacy, name="privacy"),
    path("terminos/", views.terms, name="terms"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
    path(
        "solicitudes/<uuid:request_id>/adjunto/",
        views.request_attachment_download,
        name="request_attachment_download",
    ),
]
