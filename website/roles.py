from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth.models import Group, Permission
from django.db import transaction


ROLE_GROUP_NAMES = {
    "owner": "CW · Owner",
    "admin": "CW · Administrador",
    "technician": "CW · Técnico",
    "content_manager": "CW · Contenido",
    "viewer": "CW · Solo lectura",
}

CONTENT_MODELS = {
    "sitesettings",
    "servicecategory",
    "service",
    "coveragezone",
    "brand",
    "servicebrand",
    "faqitem",
    "portfolioproject",
    "portfoliovideo",
    "brandvideo",
    "customerreview",
    "holiday",
    "paymentmethod",
    "redirectrule",
}


def _permissions_for_models(
    models: Iterable[str],
    actions: Iterable[str] = ("add", "change", "delete", "view"),
) -> Permission.objects.none().__class__:
    query = Permission.objects.none()
    for model_name in models:
        for action in actions:
            query |= Permission.objects.filter(
                content_type__app_label="website",
                content_type__model=model_name,
                codename=f"{action}_{model_name}",
            )
    return query


@transaction.atomic
def provision_role_groups() -> None:
    groups = {
        role: Group.objects.get_or_create(name=name)[0]
        for role, name in ROLE_GROUP_NAMES.items()
    }
    for group in groups.values():
        group.permissions.clear()

    website_permissions = Permission.objects.filter(content_type__app_label="website")
    groups["owner"].permissions.add(*website_permissions)
    groups["owner"].permissions.add(
        *Permission.objects.filter(content_type__app_label="auth")
    )

    admin_permissions = website_permissions.exclude(
        codename__in=("restore_backuprecord",)
    )
    groups["admin"].permissions.add(*admin_permissions)
    groups["admin"].permissions.add(
        *Permission.objects.filter(
            content_type__app_label="auth",
            content_type__model__in=("user", "group"),
            codename__regex=r"^(add|change|view)_",
        )
    )

    technician_permissions = Permission.objects.filter(
        content_type__app_label="website",
        codename__in=(
            "view_servicerequest",
            "change_servicerequest",
            "view_customer",
            "view_service",
            "view_servicerequestevent",
            "view_servicerequestnote",
            "add_servicerequestnote",
            "change_servicerequestnote",
        ),
    )
    groups["technician"].permissions.add(*technician_permissions)

    groups["content_manager"].permissions.add(*_permissions_for_models(CONTENT_MODELS))

    viewer_permissions = Permission.objects.filter(
        content_type__app_label="website",
        codename__startswith="view_",
    ).exclude(
        content_type__model__in=(
            "auditevent",
            "backuprecord",
            "exportrecord",
            "loginevent",
            "privacyrequest",
        )
    )
    groups["viewer"].permissions.add(*viewer_permissions)


def sync_user_role(profile) -> None:
    managed_names = tuple(ROLE_GROUP_NAMES.values())
    profile.user.groups.remove(*Group.objects.filter(name__in=managed_names))
    group = Group.objects.filter(name=ROLE_GROUP_NAMES[profile.role]).first()
    if group:
        profile.user.groups.add(group)
