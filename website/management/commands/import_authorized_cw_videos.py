"""Importa únicamente los dos archivos de trabajo autorizados en septiembre de 2026.

Los originales se conservan en almacenamiento privado. La operación nunca
sobrescribe casos o archivos existentes y publica cada caso solo al final.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from website.models import PortfolioProject, PortfolioVideo, Service, SiteSettings
from website.validators import (
    validate_image_upload,
    validate_private_original_video,
    validate_public_video,
)


SOURCES = (
    {
        "key": "lavadora-revision",
        "slug": "revision-interna-lavadora",
        "title": "Revisión interna de una lavadora",
        "equipment": "Lavadora",
        "service_slug": "lavadoras",
        "municipality": "",
        "description": (
            "Registro visual de componentes internos de una lavadora durante "
            "un trabajo técnico de CW Reparaciones."
        ),
        "sha256": "9b7e5cf6d1edb376c2140d2be4e34e221d27416cde5ab84a9c29b20b75469e66",
        "duration": 58,
    },
    {
        "key": "equipo-comercial",
        "slug": "mantenimiento-equipo-cafeteria",
        "title": "Trabajo técnico en una máquina de cafetería",
        "equipment": "Máquina de cafetería",
        "service_slug": "",
        "municipality": "Envigado",
        "description": (
            "Registro visual de un equipo de cafetería abierto y sus componentes "
            "durante un trabajo técnico de CW Reparaciones."
        ),
        "sha256": "2ad0765e81b27a00494b1d619a3805b95a52b1b3f79ee5a0483aae8ed40261dd",
        "duration": 59,
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Importa dos trabajos audiovisuales propios con autorización confirmada."

    def add_arguments(self, parser):
        parser.add_argument("--original-lavadora", required=True, type=Path)
        parser.add_argument("--original-cafeteria", required=True, type=Path)
        parser.add_argument(
            "--derivatives-directory",
            type=Path,
            default=Path(settings.BASE_DIR) / "media_work",
        )
        parser.add_argument("--authorization-confirmed", action="store_true")

    def handle(self, *args, **options):
        if not options["authorization_confirmed"]:
            raise CommandError("Confirma la autorización antes de importar/publicar.")

        source_paths = (
            options["original_lavadora"],
            options["original_cafeteria"],
        )
        derivative_directory = options["derivatives_directory"]
        prepared = []
        for spec, source_path in zip(SOURCES, source_paths, strict=True):
            paths = {
                "original": source_path,
                "preview": derivative_directory / f"{spec['key']}-preview.mp4",
                "full": derivative_directory / f"{spec['key']}-full.mp4",
                "poster": derivative_directory / f"{spec['key']}-poster.jpg",
            }
            for label, path in paths.items():
                if not path.is_file():
                    raise CommandError(f"Falta {label}: {path}")
            if _sha256(source_path) != spec["sha256"]:
                raise CommandError(f"El original no coincide con el archivo revisado: {source_path}")
            for label, validator in (
                ("original", validate_private_original_video),
                ("preview", validate_public_video),
                ("full", validate_public_video),
                ("poster", validate_image_upload),
            ):
                with paths[label].open("rb") as stream:
                    validator(stream)
            prepared.append((spec, paths))

        for spec, paths in prepared:
            existing = PortfolioProject.objects.filter(slug=spec["slug"]).first()
            if existing:
                if existing.is_published and existing.published_videos.exists():
                    self.stdout.write(f"Ya publicado: {existing.title}")
                    continue
                draft_video = existing.videos.filter(title=spec["title"], is_published=False).first()
                if (
                    existing.title != spec["title"]
                    or existing.is_published
                    or draft_video is None
                    or any(
                        getattr(draft_video, field).name
                        for field in ("original_video", "preview_video", "full_video", "poster_image")
                    )
                ):
                    raise CommandError(
                        f"Existe un caso parcial con slug {spec['slug']}; revísalo en el admin antes de reintentar."
                    )
                project = existing
                video = draft_video
            else:
                service = (
                    Service.objects.filter(slug=spec["service_slug"], is_active=True).first()
                    if spec["service_slug"]
                    else None
                )
                if spec["service_slug"] and service is None:
                    raise CommandError(f"No existe el servicio {spec['service_slug']}.")

                authorization_note = (
                    "El usuario confirmó el 15-09-2026 que este video muestra un trabajo "
                    "propio de CW Reparaciones y autorizó publicar personas, espacios, "
                    "audio y datos visibles."
                )
                project = PortfolioProject.objects.create(
                    slug=spec["slug"],
                    title=spec["title"],
                    equipment=spec["equipment"],
                    municipality=spec["municipality"],
                    work_performed=spec["description"],
                    service=service,
                    is_featured=True,
                    authorization_status=PortfolioProject.AuthorizationStatus.AUTHORIZED,
                    authorization_notes=authorization_note,
                    is_published=False,
                )
                video = PortfolioVideo.objects.create(
                    project=project,
                    title=spec["title"],
                    description=spec["description"],
                    duration_seconds=spec["duration"],
                    width=720,
                    height=1280,
                    authorization_status=PortfolioVideo.AuthorizationStatus.AUTHORIZED,
                    authorization_notes=authorization_note,
                    is_featured=True,
                    is_published=False,
                )
            for field_name, path_key in (
                ("original_video", "original"),
                ("preview_video", "preview"),
                ("full_video", "full"),
                ("poster_image", "poster"),
            ):
                with paths[path_key].open("rb") as stream:
                    getattr(video, field_name).save(
                        paths[path_key].name, File(stream), save=True
                    )
            video.full_clean()
            project.is_published = True
            project.full_clean()
            project.save()
            video.is_published = True
            video.full_clean()
            video.save()
            self.stdout.write(self.style.SUCCESS(f"Publicado: {project.title}"))

        settings_object = SiteSettings.load()
        if PortfolioProject.objects.filter(is_published=True).exists():
            settings_object.feature_portfolio = True
            settings_object.save()
