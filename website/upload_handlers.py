from __future__ import annotations

from pathlib import Path

from django.core.exceptions import RequestDataTooBig, TooManyFilesSent
from django.core.files.uploadhandler import FileUploadHandler

from .validators import MAX_IMAGE_SIZE, MAX_VIDEO_SIZE


class ServiceRequestUploadHandler(FileUploadHandler):
    """Corta cargas abusivas mientras llegan, antes de validarlas o guardarlas."""

    def __init__(self, request=None):
        super().__init__(request)
        self.file_count = 0
        self.received_bytes = 0
        self.maximum_bytes = MAX_IMAGE_SIZE

    def new_file(
        self,
        field_name,
        file_name,
        content_type,
        content_length,
        charset=None,
        content_type_extra=None,
    ):
        super().new_file(
            field_name,
            file_name,
            content_type,
            content_length,
            charset,
            content_type_extra,
        )
        self.file_count += 1
        if self.file_count > 1:
            raise TooManyFilesSent("Solo se permite un archivo por solicitud.")

        self.received_bytes = 0
        self.maximum_bytes = (
            MAX_VIDEO_SIZE
            if Path(file_name or "").suffix.lower() == ".mp4"
            else MAX_IMAGE_SIZE
        )
        if content_length is not None and content_length > self.maximum_bytes:
            raise RequestDataTooBig("El archivo supera el tamaño permitido.")

    def receive_data_chunk(self, raw_data, start):
        self.received_bytes += len(raw_data)
        if self.received_bytes > self.maximum_bytes:
            raise RequestDataTooBig("El archivo supera el tamaño permitido.")
        return raw_data

    def file_complete(self, file_size):
        return None
