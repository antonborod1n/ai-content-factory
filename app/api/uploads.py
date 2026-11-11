"""Bounded reads of multipart uploads."""

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

_CHUNK_BYTES = 1024 * 1024


def _too_large(limit_mb: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail=f"File is larger than {limit_mb} MB",
    )


async def read_upload(file: UploadFile) -> bytes:
    """Read an upload, stopping with 413 once it exceeds ``MAX_UPLOAD_MB``."""
    limit_mb = get_settings().max_upload_mb
    limit = limit_mb * 1024 * 1024
    if file.size is not None and file.size > limit:
        raise _too_large(limit_mb)
    buffer = bytearray()
    while chunk := await file.read(_CHUNK_BYTES):
        buffer.extend(chunk)
        if len(buffer) > limit:
            raise _too_large(limit_mb)
    return bytes(buffer)
