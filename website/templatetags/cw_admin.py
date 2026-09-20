from __future__ import annotations

from django import template
from django.db import connection
from django.db.models import Count
from django.utils import timezone

from website.models import BackupRecord, Customer, ExportRecord, ServiceRequest, UserProfile


register = template.Library()


@register.simple_tag(takes_context=True)
def cw_dashboard(context):
    request = context["request"]
    requests = ServiceRequest.objects.filter(is_deleted=False)
    profile = getattr(request.user, "cw_profile", None)
    if profile and profile.role == UserProfile.Role.TECHNICIAN:
        requests = requests.filter(assigned_technician=request.user)

    today = timezone.localdate()
    month_start = today.replace(day=1)
    recent = requests.select_related("service", "assigned_technician")[:8]
    status_counts = dict(
        requests.values_list("status").annotate(total=Count("pk"))
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database_status = "Operativa"
        database_ok = True
    except Exception:
        database_status = "Requiere revisión"
        database_ok = False

    latest_backup = BackupRecord.objects.filter(status=BackupRecord.Status.READY).first()
    notifications = []
    new_count = status_counts.get(ServiceRequest.Status.NEW, 0)
    unassigned_count = requests.filter(
        assigned_technician__isnull=True,
    ).exclude(status__in=(ServiceRequest.Status.COMPLETED, ServiceRequest.Status.CANCELLED)).count()
    if new_count:
        notifications.append(f"{new_count} solicitud(es) nueva(s) requieren revisión.")
    if unassigned_count:
        notifications.append(f"{unassigned_count} solicitud(es) activa(s) aún no tienen técnico.")

    return {
        "total": requests.count(),
        "new": new_count,
        "active": requests.exclude(status__in=(ServiceRequest.Status.COMPLETED, ServiceRequest.Status.CANCELLED)).count(),
        "completed_month": requests.filter(status=ServiceRequest.Status.COMPLETED, completed_at__date__gte=month_start).count(),
        "scheduled": status_counts.get(ServiceRequest.Status.SCHEDULED, 0),
        "unassigned": unassigned_count,
        "customers": Customer.objects.filter(is_deleted=False).count(),
        "recent": recent,
        "notifications": notifications,
        "database_status": database_status,
        "database_ok": database_ok,
        "latest_backup": latest_backup,
        "exports_ready": ExportRecord.objects.filter(created_by=request.user, status=ExportRecord.Status.READY, expires_at__gt=timezone.now()).count(),
    }
