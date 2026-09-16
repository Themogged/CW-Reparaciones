from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

from django.core.exceptions import ValidationError


MEBIBYTE = 1024 * 1024
MAX_IMAGE_SIZE = 8 * MEBIBYTE
MAX_VIDEO_SIZE = 20 * MEBIBYTE
MAX_PUBLIC_VIDEO_SIZE = 30 * MEBIBYTE
MAX_PRIVATE_VIDEO_SIZE = 250 * MEBIBYTE

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4"}

MIME_BY_KIND = {
    "jpeg": {"image/jpeg", "image/pjpeg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
    "mp4": {"video/mp4", "application/mp4"},
}

KIND_BY_EXTENSION = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
    ".mp4": "mp4",
}

PHONE_CHARACTERS = re.compile(r"^\+?[0-9().\- ]+$")


def validate_phone_number(value: str) -> None:
    """Admite formato internacional legible y exige entre 7 y 15 dígitos."""

    if not PHONE_CHARACTERS.fullmatch(value or ""):
        raise ValidationError(
            "Ingresa un número de contacto válido.", code="invalid_phone"
        )
    digit_count = sum(character.isdigit() for character in value)
    if not 7 <= digit_count <= 15:
        raise ValidationError(
            "Ingresa un número de contacto válido.", code="invalid_phone"
        )


def _safe_file_size(uploaded_file: BinaryIO) -> int:
    size = getattr(uploaded_file, "size", None)
    if size is not None:
        return int(size)

    original_position = uploaded_file.tell()
    uploaded_file.seek(0, 2)
    size = uploaded_file.tell()
    uploaded_file.seek(original_position)
    return size


def _read_edges(uploaded_file: BinaryIO, head_size: int = 32) -> tuple[bytes, bytes]:
    original_position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        head = uploaded_file.read(head_size)
        uploaded_file.seek(0, 2)
        size = uploaded_file.tell()
        uploaded_file.seek(max(0, size - 16))
        tail = uploaded_file.read(16)
    finally:
        uploaded_file.seek(original_position)
    return head, tail


def _detected_kind(head: bytes, tail: bytes, size: int) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n") and tail.endswith(
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    ):
        return "png"
    if head.startswith(b"\xff\xd8\xff") and tail.endswith(b"\xff\xd9"):
        return "jpeg"
    if len(head) >= 16 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        declared_size = int.from_bytes(head[4:8], byteorder="little", signed=False)
        if declared_size + 8 == size and head[12:16] in {b"VP8 ", b"VP8L", b"VP8X"}:
            return "webp"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        box_size = int.from_bytes(head[:4], byteorder="big", signed=False)
        if box_size == 1 or 12 <= box_size <= size:
            return "mp4"
    return None


def _validate_upload(
    uploaded_file: BinaryIO, *, allow_video: bool, video_size_limit: int = MAX_VIDEO_SIZE
) -> None:
    if not uploaded_file:
        return

    extension = Path(getattr(uploaded_file, "name", "")).suffix.lower()
    permitted_extensions = IMAGE_EXTENSIONS | (VIDEO_EXTENSIONS if allow_video else set())
    if extension not in permitted_extensions:
        raise ValidationError(
            "Formato no permitido. Usa JPEG, PNG o WebP"
            + (", o MP4." if allow_video else "."),
            code="invalid_extension",
        )

    size = _safe_file_size(uploaded_file)
    if size <= 0:
        raise ValidationError("El archivo está vacío.", code="empty_file")

    expected_kind = KIND_BY_EXTENSION[extension]
    maximum_size = video_size_limit if expected_kind == "mp4" else MAX_IMAGE_SIZE
    if size > maximum_size:
        limit_mb = maximum_size // MEBIBYTE
        raise ValidationError(
            f"El archivo supera el límite de {limit_mb} MB.",
            code="file_too_large",
        )

    try:
        head, tail = _read_edges(uploaded_file)
    except (AttributeError, OSError, ValueError) as exc:
        raise ValidationError(
            "No se pudo leer el archivo adjunto.", code="unreadable_file"
        ) from exc

    detected_kind = _detected_kind(head, tail, size)
    if detected_kind != expected_kind:
        raise ValidationError(
            "El contenido del archivo no coincide con su extensión.",
            code="invalid_signature",
        )

    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type and content_type not in MIME_BY_KIND[detected_kind]:
        raise ValidationError(
            "El tipo MIME del archivo no es válido.", code="invalid_mime_type"
        )


def validate_image_upload(uploaded_file: BinaryIO) -> None:
    """Valida extensión, tamaño, MIME y firma de una imagen admitida."""

    _validate_upload(uploaded_file, allow_video=False)


def validate_diagnostic_media(uploaded_file: BinaryIO) -> None:
    """Valida imágenes y videos MP4 adjuntos a una solicitud."""

    _validate_upload(uploaded_file, allow_video=True)


def validate_public_video(uploaded_file: BinaryIO) -> None:
    if Path(getattr(uploaded_file, "name", "")).suffix.lower() != ".mp4":
        raise ValidationError("Usa un video MP4.", code="invalid_video_extension")
    _validate_upload(uploaded_file, allow_video=True, video_size_limit=MAX_PUBLIC_VIDEO_SIZE)


def validate_private_original_video(uploaded_file: BinaryIO) -> None:
    if Path(getattr(uploaded_file, "name", "")).suffix.lower() != ".mp4":
        raise ValidationError("Usa un video MP4.", code="invalid_video_extension")
    _validate_upload(uploaded_file, allow_video=True, video_size_limit=MAX_PRIVATE_VIDEO_SIZE)
