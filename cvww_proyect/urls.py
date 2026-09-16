"""Root URL configuration for CW Reparaciones."""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("website.urls", "website"), namespace="website")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "website.views.error_404"
handler500 = "website.views.error_500"
