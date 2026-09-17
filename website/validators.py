from __future__ import annotations

import io
import re
import warnings
from pathlib import Path
from typing import BinaryIO

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MEBIBYTE = 1024 * 1024
MAX_IMAGE_SIZE = 8 * MEBIBYTE
MAX_VIDEO_SIZE = 20 * MEBIBYTE
MAX_PUBLIC_VIDEO_SIZE = 30 * MEBIBYTE
MAX_PRIVATE_VIDEO_SIZE = 250 * MEBIBYTE
MAX_IMAGE_PIXELS = 40_000_000

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


def _validate_decodable_image(uploaded_file: BinaryIO, expected_kind: str) -> None:
    original_position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        payload = uploaded_file.read(MAX_IMAGE_SIZE + 1)
    finally:
        uploaded_file.seek(original_position)

    expected_format = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[expected_kind]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as image:
                width, height = image.size
                if image.format != expected_format:
                    raise ValidationError(
                        "El contenido de la imagen no coincide con su extensión.",
                        code="invalid_image_format",
                    )
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise ValidationError(
                        "La imagen tiene dimensiones no permitidas.",
                        code="unsafe_image_dimensions",
                    )
                image.verify()
    except ValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise ValidationError(
            "La imagen está dañada o no puede validarse de forma segura.",
            code="invalid_image_payload",
        ) from exc


def _validate_mp4_structure(uploaded_file: BinaryIO, size: int) -> None:
    original_position = uploaded_file.tell()
    offset = 0
    boxes: set[bytes] = set()
    try:
        while offset + 8 <= size:
            uploaded_file.seek(offset)
            header = uploaded_file.read(16)
            if len(header) < 8:
                break

            box_size = int.from_bytes(header[:4], byteorder="big", signed=False)
            box_type = header[4:8]
            header_size = 8
            if box_size == 1:
                if len(header) < 16:
                    break
                box_size = int.from_bytes(header[8:16], byteorder="big", signed=False)
                header_size = 16
            elif box_size == 0:
                box_size = size - offset

            if box_size < header_size or offset + box_size > size:
                break
            boxes.add(box_type)
            offset += box_size
            if box_size == 0:
                break
    except (AttributeError, OSError, ValueError) as exc:
        raise ValidationError(
            "No se pudo inspeccionar la estructura del video.",
            code="unreadable_video",
        ) from exc
    finally:
        uploaded_file.seek(original_position)

    if offset != size or b"ftyp" not in boxes or b"moov" not in boxes or not (
        {b"mdat", b"moof"} & boxes
    ):
        raise ValidationError(
            "El video MP4 está incompleto o tiene una estructura no válida.",
            code="invalid_video_structure",
        )


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

    if detected_kind == "mp4":
        _validate_mp4_structure(uploaded_file, size)
    else:
        _validate_decodable_image(uploaded_file, detected_kind)

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
