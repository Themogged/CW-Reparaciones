import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.test import SimpleTestCase
from PIL import Image

from website.validators import (
    MAX_IMAGE_SIZE,
    validate_diagnostic_media,
    validate_image_upload,
)


def _image_bytes(image_format: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), (12, 56, 90)).save(output, format=image_format)
    return output.getvalue()


VALID_JPEG = _image_bytes("JPEG")
VALID_PNG = _image_bytes("PNG")
VALID_WEBP = _image_bytes("WEBP")
VALID_MP4 = (
    b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isommp41"
    b"\x00\x00\x00\x08moov"
    b"\x00\x00\x00\x08mdat"
)


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

    def test_rejects_image_with_valid_edges_but_invalid_payload(self):
        upload = SimpleUploadedFile(
            "fake.jpg",
            b"\xff\xd8\xff\xe0not-a-decodable-image\xff\xd9",
            content_type="image/jpeg",
        )
        with self.assertRaisesMessage(ValidationError, "dañada"):
            validate_image_upload(upload)

    def test_rejects_mp4_with_only_file_type_box(self):
        upload = SimpleUploadedFile(
            "incomplete.mp4",
            b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isommp41",
            content_type="video/mp4",
        )
        with self.assertRaisesMessage(ValidationError, "incompleto"):
            validate_diagnostic_media(upload)

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
