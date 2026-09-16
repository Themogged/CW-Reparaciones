"""Importa la pieza audiovisual CW confirmada, sin tratarla como caso técnico."""

from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from website.models import BrandVideo
from website.validators import (
    validate_image_upload,
    validate_private_original_video,
    validate_public_video,
)


TITLE = "Presentación audiovisual de CW Reparaciones"
SOURCE_SHA256 = "32cffb26fce5e086835285974e2bc43a1b56ef8e9a14741ec565a88e946506a5"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Importa el video de marca CW autorizado el 15-09-2026."

    def add_arguments(self, parser):
        parser.add_argument("--original", required=True, type=Path)
        parser.add_argument(
            "--derivatives-directory",
            type=Path,
            default=Path(settings.BASE_DIR) / "media_work",
        )
        parser.add_argument("--authorization-confirmed", action="store_true")

    def handle(self, *args, **options):
        if not options["authorization_confirmed"]:
            raise CommandError("Confirma la autorización del video y su audio antes de importar.")

        original = options["original"]
        derivatives = options["derivatives_directory"]
        paths = {
            "original_video": original,
            "preview_video": derivatives / "cw-presentacion-preview.mp4",
            "full_video": derivatives / "cw-presentacion-full.mp4",
            "poster_image": derivatives / "cw-presentacion-poster.jpg",
        }
        for name, path in paths.items():
            if not path.is_file():
                raise CommandError(f"Falta {name}: {path}")
        if _sha256(original) != SOURCE_SHA256:
            raise CommandError("El original no coincide con el video de marca revisado.")

        for name, validator in (
            ("original_video", validate_private_original_video),
            ("preview_video", validate_public_video),
            ("full_video", validate_public_video),
            ("poster_image", validate_image_upload),
        ):
            with paths[name].open("rb") as stream:
                validator(File(stream, name=paths[name].name))

        existing = BrandVideo.objects.filter(title=TITLE).first()
        if existing:
            if existing.is_published and existing.authorization_status == BrandVideo.AuthorizationStatus.AUTHORIZED:
                self.stdout.write("Ya publicado: video de marca CW.")
                return
            if existing.authorization_status != BrandVideo.AuthorizationStatus.AUTHORIZED or any(
                getattr(existing, name).name for name in paths
            ):
                raise CommandError("Existe una importación parcial; revísala en el admin antes de reintentar.")
            video = existing
        else:
            video = BrandVideo.objects.create(
                title=TITLE,
                description="Presentación audiovisual de CW Reparaciones con imágenes de equipos técnicos.",
                duration_seconds=21,
                authorization_status=BrandVideo.AuthorizationStatus.AUTHORIZED,
                authorization_notes=(
                    "El usuario confirmó el 15-09-2026 que el video de marca es de CW "
                    "Reparaciones y autorizó publicarlo con música, voz, personas y espacios visibles."
                ),
            )
        for name, path in paths.items():
            with path.open("rb") as stream:
                getattr(video, name).save(path.name, File(stream), save=True)
        video.is_published = True
        video.full_clean()
        video.save()
        self.stdout.write(self.style.SUCCESS("Publicado: video de marca CW."))
