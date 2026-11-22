"""Safe file handling for uploads and generated documents."""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from pathlib import Path

from fastapi import HTTPException, status

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")
_MULTI_UNDERSCORE = re.compile(r"_{2,}")
_MAX_STORED_NAME = 80
_MAX_ORIGINAL_DISPLAY = 180


def sanitise_filename(filename: str | None) -> str:
    """Return a safe display filename. Never returns a path."""
    if not filename:
        return "document"
    # Strip any directory component the client may have sent.
    base = filename.replace("\\", "/").split("/")[-1]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = _UNSAFE_CHARS.sub("_", base).strip(" ._")
    base = _MULTI_UNDERSCORE.sub("_", base)
    if not base:
        return "document"
    if len(base) > _MAX_ORIGINAL_DISPLAY:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: _MAX_ORIGINAL_DISPLAY - len(ext) - 1] + dot + ext) if dot else base[:_MAX_ORIGINAL_DISPLAY]
    return base


def validate_extension(filename: str, allowed: tuple[str, ...]) -> str:
    suffix = Path(sanitise_filename(filename)).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{suffix or 'unknown'}'. "
                f"Allowed types: {', '.join(allowed)}."
            ),
        )
    return ALLOWED_EXTENSIONS[suffix]


def validate_content_type(
    content_type: str | None, allowed: tuple[str, ...]
) -> None:
    if not content_type:
        return
    normalised = content_type.split(";")[0].strip().lower()
    if normalised not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{normalised}' is not accepted.",
        )


def validate_size(size: int, max_bytes: int) -> None:
    if size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty."
        )
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is larger than the {max_bytes // (1024 * 1024)}MB limit.",
        )


def build_storage_path(directory: Path, file_type: str, original_filename: str) -> tuple[str, str, str]:
    """Return (stored_filename, absolute_path, content_hash) for a new upload.

    The on-disk name is fully generated, so the client's filename is never used
    as a path component and cannot escape the storage directory.
    """
    content_hash = uuid.uuid4().hex
    stored_name = f"{content_hash}.{file_type}"
    destination = (directory / stored_name).resolve()
    directory_resolved = directory.resolve()
    if directory_resolved not in destination.parents:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Refusing to write outside the storage directory.",
        )
    return stored_name, str(destination), content_hash


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_read_text(path: str, max_bytes: int = 5 * 1024 * 1024) -> str:
    """Read a stored file defensively. Never raises on size/content surprises."""
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is missing."
        )
    with resolved.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Stored document is too large to read."
        )
    return data.decode("utf-8", errors="replace")


__all__ = [
    "ALLOWED_EXTENSIONS",
    "build_storage_path",
    "safe_read_text",
    "sanitise_filename",
    "sha256_of",
    "validate_content_type",
    "validate_extension",
    "validate_size",
]
