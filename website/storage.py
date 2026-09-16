from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateServiceRequestStorage(FileSystemStorage):
    """Almacenamiento local sin URL pública para adjuntos de solicitudes."""

    def __init__(self) -> None:
        location = getattr(
            settings,
            "WEBSITE_PRIVATE_MEDIA_ROOT",
            Path(settings.BASE_DIR) / "private_uploads",
        )
        super().__init__(
            location=location,
            base_url=None,
            file_permissions_mode=0o600,
            directory_permissions_mode=0o700,
        )

    def url(self, name: str) -> str:
        raise ValueError("Los archivos de solicitudes no tienen una URL pública.")


private_service_request_storage = PrivateServiceRequestStorage()

