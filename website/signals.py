from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.exceptions import ValidationError
from django.db.models.signals import post_migrate, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import AuditEvent, LoginEvent, UserProfile
from .roles import provision_role_groups, sync_user_role


def _client_ip(request) -> str | None:
    if request is None:
        return None
    value = request.META.get("REMOTE_ADDR", "")
    return value or None


def _user_agent(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:500]


@receiver(post_migrate)
def provision_roles(sender, **kwargs) -> None:
    if sender.name != "website":
        return
    provision_role_groups()
    for user in get_user_model().objects.all().iterator():
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "role": UserProfile.Role.OWNER if user.is_superuser else UserProfile.Role.VIEWER
            },
        )
        if created:
            sync_user_role(profile)


@receiver(post_save, sender=UserProfile)
def update_role_group(sender, instance: UserProfile, created: bool, **kwargs) -> None:
    # Crear una cuenta no debe conceder acceso implícito a datos privados. El
    # grupo se asigna al guardar explícitamente el perfil o al aprovisionar una
    # instalación existente mediante post_migrate.
    if not created:
        sync_user_role(instance)


@receiver(pre_save, sender=UserProfile)
def protect_last_owner_change(sender, instance: UserProfile, **kwargs) -> None:
    if not instance.pk:
        return
    previous_role = sender.objects.filter(pk=instance.pk).values_list("role", flat=True).first()
    if previous_role != UserProfile.Role.OWNER or instance.role == UserProfile.Role.OWNER:
        return
    active_owners = sender.objects.filter(
        role=UserProfile.Role.OWNER,
        user__is_active=True,
    ).exclude(pk=instance.pk)
    if not active_owners.exists():
        raise ValidationError("No se puede quitar el rol al último OWNER activo.")


@receiver(pre_delete, sender=UserProfile)
def protect_last_owner_profile(sender, instance: UserProfile, **kwargs) -> None:
    if instance.role != UserProfile.Role.OWNER:
        return
    if not sender.objects.filter(
        role=UserProfile.Role.OWNER,
        user__is_active=True,
    ).exclude(pk=instance.pk).exists():
        raise ValidationError("No se puede eliminar el perfil del último OWNER activo.")


@receiver(post_save, sender=get_user_model())
def ensure_user_profile(sender, instance, created: bool, **kwargs) -> None:
    if not created:
        return
    UserProfile.objects.get_or_create(
        user=instance,
        defaults={
            "role": UserProfile.Role.OWNER if instance.is_superuser else UserProfile.Role.VIEWER
        },
    )


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs) -> None:
    LoginEvent.objects.create(
        user=user,
        username=user.get_username(),
        success=True,
        event="login",
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.LOGIN,
        object_type="auth.user",
        object_id=str(user.pk),
        object_repr=user.get_username(),
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@receiver(user_logged_out)
def record_logout(sender, request, user, **kwargs) -> None:
    if user is None:
        return
    LoginEvent.objects.create(
        user=user,
        username=user.get_username(),
        success=True,
        event="logout",
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.LOGOUT,
        object_type="auth.user",
        object_id=str(user.pk),
        object_repr=user.get_username(),
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@receiver(user_login_failed)
def record_failed_login(sender, credentials, request, **kwargs) -> None:
    username = str(credentials.get("username", ""))[:150]
    LoginEvent.objects.create(
        username=username,
        success=False,
        event="login",
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    AuditEvent.objects.create(
        action=AuditEvent.Action.LOGIN_FAILED,
        object_type="auth.user",
        object_repr=username,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
