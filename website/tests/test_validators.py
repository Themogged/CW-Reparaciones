import base64
import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.test import SimpleTestCase

from website.validators import (
    MAX_IMAGE_SIZE,
    validate_diagnostic_media,
    validate_image_upload,
)


VALID_JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-data" + b"\xff\xd9"
VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
VALID_WEBP = b"RIFF\x0c\x00\x00\x00WEBPVP8 \x00\x00\x00\x00"
VALID_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isommp41"


class UploadValidatorTests(SimpleTestCase):
    def test_accepts_supported_signatures(self):
        cases = (
            ("image.jpg", VALID_JPEG, "image/jpeg", validate_image_upload),
            ("image.png", VALID_PNG, "image/png", validate_image_upload),
            ("image.webp", VALID_WEBP, "image/webp", validate_image_upload),
            ("video.mp4", VALID_MP4, "video/mp4", validate_diagnostic_media),
        )
        for name, content, content_type, validator in cases:
            with self.subTest(name=name):
                validator(SimpleUploadedFile(name, content, content_type=content_type))

    def test_rejects_extension_signature_mismatch(self):
        upload = SimpleUploadedFile("fake.png", VALID_JPEG, content_type="image/png")
        with self.assertRaisesMessage(ValidationError, "no coincide"):
            validate_image_upload(upload)

    def test_rejects_spoofed_mime_type(self):
        upload = SimpleUploadedFile("image.png", VALID_PNG, content_type="text/plain")
        with self.assertRaisesMessage(ValidationError, "MIME"):
            validate_image_upload(upload)

    def test_rejects_truncated_png_without_end_marker(self):
        upload = SimpleUploadedFile(
            "truncated.png", b"\x89PNG\r\n\x1a\ncontent", content_type="image/png"
        )
        with self.assertRaisesMessage(ValidationError, "no coincide"):
            validate_image_upload(upload)

    def test_rejects_webp_with_inconsistent_container_size(self):
        upload = SimpleUploadedFile(
            "broken.webp",
            b"RIFF\xff\x00\x00\x00WEBPVP8 \x00\x00\x00\x00",
            content_type="image/webp",
        )
        with self.assertRaisesMessage(ValidationError, "no coincide"):
            validate_image_upload(upload)

    def test_rejects_phone_with_embedded_newline_or_misplaced_plus(self):
        from website.validators import validate_phone_number

        for value in ("0991234\n567", "099+1234567"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_phone_number(value)

    def test_image_validator_rejects_mp4(self):
        upload = SimpleUploadedFile("video.mp4", VALID_MP4, content_type="video/mp4")
        with self.assertRaisesMessage(ValidationError, "Formato no permitido"):
            validate_image_upload(upload)

    def test_rejects_file_above_size_limit_without_loading_it(self):
        upload = UploadedFile(
            file=io.BytesIO(VALID_PNG),
            name="large.png",
            content_type="image/png",
            size=MAX_IMAGE_SIZE + 1,
        )
        with self.assertRaisesMessage(ValidationError, "límite"):
            validate_image_upload(upload)

    def test_restores_file_position_after_validation(self):
        upload = SimpleUploadedFile("image.png", VALID_PNG, content_type="image/png")
        upload.seek(3)
        validate_image_upload(upload)
        self.assertEqual(upload.tell(), 3)
