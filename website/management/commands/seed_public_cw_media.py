"""Instala derivados audiovisuales autorizados incluidos en el repositorio.

Los originales privados no forman parte del paquete Git. Este comando crea
registros públicos únicamente a partir de previews, versiones web y pósteres
cuya integridad se comprueba antes de modificar la base de datos.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from website.management.commands.import_authorized_cw_brand_video import TITLE as BRAND_TITLE
from website.management.commands.import_authorized_cw_videos import SOURCES
from website.models import BrandVideo, PortfolioProject, PortfolioVideo, Service, SiteSettings
from website.validators import validate_image_upload, validate_public_video


BUNDLE_HASHES = {
    "lavadora-revision-preview.mp4": "0b574246afe4e06f9092c93c66aa931a90ced9676a943e24538f10a60b2aafbe",
    "lavadora-revision-full.mp4": "deaab9c6aff4a4289089082d86d74ddd161c85ba9e6b1a1780380bf54c07e207",
    "lavadora-revision-poster.jpg": "04e6248a3c33c3384f2111214629dcafb6407652a3e08717c8c3c533166f46b1",
    "equipo-comercial-preview.mp4": "7a65cd492ef1399aa4e142b234467f9b461124860daa112488b44cf4605a7625",
    "equipo-comercial-full.mp4": "a04e92ac48525de594ef880e16c3cbc9a95088701ef28bac7700459da2de121c",
    "equipo-comercial-poster.jpg": "a54384b689850971a28b76246b443743ec7355b0d523fb9d57ec4e55aef45928",
    "cw-presentacion-preview.mp4": "e814895ad8f51051bd6a7500139375e6e0a0595fc6a6e6b620ce08e41c58157f",
    "cw-presentacion-full.mp4": "00eb2eedac50e08b2796c0f36fe6cdf9d8c11ba3e985d21b6daf73f1134db693",
    "cw-presentacion-poster.jpg": "c08a029fbe4c9545e0f52d56307472a2084acef3e837cb2e7e9e53c9ef04921e",
}

AUTHORIZATION_NOTE = (
    "El usuario confirmó el 15-09-2026 que los videos pertenecen a CW "
    "Reparaciones y autorizó su publicación, incluidas las personas, "
    "espacios, audio y datos visibles. Solo se instala el material web "
    "optimizado; los originales permanecen fuera del repositorio."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_bundle(directory: Path) -> dict[str, Path]:
    prepared = {}
    for name, expected_hash in BUNDLE_HASHES.items():
        path = directory / name
        if not path.is_file():
            raise CommandError(f"Falta el derivado autorizado: {path}")
        if _sha256(path) != expected_hash:
            raise CommandError(f"El derivado no coincide con el archivo revisado: {name}")
        validator = validate_image_upload if name.endswith(".jpg") else validate_public_video
        with path.open("rb") as stream:
            validator(File(stream, name=name))
        prepared[name] = path
    return prepared


def _save_public_files(video, key: str, prepared: dict[str, Path]) -> None:
    for field_name, filename in (
        ("preview_video", f"{key}-preview.mp4"),
        ("full_video", f"{key}-full.mp4"),
        ("poster_image", f"{key}-poster.jpg"),
    ):
        path = prepared[filename]
        with path.open("rb") as stream:
            getattr(video, field_name).save(filename, File(stream, name=filename), save=False)


def _existing_public_files(video) -> bool:
    return all(
        (field := getattr(video, name)).name and field.storage.exists(field.name)
        for name in ("preview_video", "full_video", "poster_image")
    )


class Command(BaseCommand):
    help = "Instala los tres videos CW autorizados desde derivados públicos empaquetados."

    def add_arguments(self, parser):
        parser.add_argument("--authorization-confirmed", action="store_true")
        parser.add_argument(
            "--bundle-directory",
            type=Path,
            default=Path(settings.BASE_DIR) / "public_media",
        )

    def handle(self, *args, **options):
        if not options["authorization_confirmed"]:
            raise CommandError("Confirma la autorización antes de instalar/publicar los videos.")
        prepared = _verify_bundle(options["bundle_directory"])

        for spec in SOURCES:
            with transaction.atomic():
                self._install_case(spec, prepared)
        with transaction.atomic():
            self._install_brand_video(prepared)

        if PortfolioProject.objects.filter(is_published=True).exists():
            site_settings = SiteSettings.load()
            if not site_settings.feature_portfolio:
                site_settings.feature_portfolio = True
                site_settings.save(update_fields=["feature_portfolio", "updated_at"])

    def _install_case(self, spec, prepared):
        project = PortfolioProject.objects.filter(slug=spec["slug"]).first()
        if project is not None:
            video = project.videos.filter(title=spec["title"], is_published=True).first()
            if project.is_published and video is not None and _existing_public_files(video):
                self.stdout.write(f"Ya publicado: {project.title}")
                return
            raise CommandError(
                f"Existe un caso parcial o con archivos ausentes ({spec['slug']}); "
                "revísalo antes de reintentar."
            )

        service = None
        if spec["service_slug"]:
            service = Service.objects.filter(slug=spec["service_slug"], is_active=True).first()
            if service is None:
                raise CommandError(f"Falta el servicio activo {spec['service_slug']}.")
        project = PortfolioProject.objects.create(
            slug=spec["slug"],
            title=spec["title"],
            equipment=spec["equipment"],
            municipality=spec["municipality"],
            work_performed=spec["description"],
            service=service,
            is_featured=True,
            authorization_status=PortfolioProject.AuthorizationStatus.AUTHORIZED,
            authorization_notes=AUTHORIZATION_NOTE,
            is_published=False,
        )
        video = PortfolioVideo(
            project=project,
            title=spec["title"],
            description=spec["description"],
            duration_seconds=spec["duration"],
            width=720,
            height=1280,
            authorization_status=PortfolioVideo.AuthorizationStatus.AUTHORIZED,
            authorization_notes=AUTHORIZATION_NOTE,
            is_featured=True,
            is_published=False,
        )
        _save_public_files(video, spec["key"], prepared)
        video.full_clean()
        video.save()
        project.is_published = True
        project.full_clean()
        project.save()
        video.is_published = True
        video.full_clean()
        video.save()
        self.stdout.write(self.style.SUCCESS(f"Publicado: {project.title}"))

    def _install_brand_video(self, prepared):
        existing = BrandVideo.objects.filter(title=BRAND_TITLE).first()
        if existing is not None:
            if existing.is_published and _existing_public_files(existing):
                self.stdout.write("Ya publicado: presentación de marca CW")
                return
            raise CommandError("Existe un video de marca parcial o con archivos ausentes; revísalo antes de reintentar.")

        video = BrandVideo(
            title=BRAND_TITLE,
            description="Presentación audiovisual de CW Reparaciones con imágenes de equipos técnicos.",
            duration_seconds=21,
            authorization_status=BrandVideo.AuthorizationStatus.AUTHORIZED,
            authorization_notes=AUTHORIZATION_NOTE,
            is_published=False,
        )
        _save_public_files(video, "cw-presentacion", prepared)
        video.full_clean()
        video.save()
        video.is_published = True
        video.full_clean()
        video.save()
        self.stdout.write(self.style.SUCCESS("Publicado: presentación de marca CW"))
