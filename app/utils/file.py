"""File handling utilities"""
import os
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/jpg",
    "application/pdf",
    "image/tiff",
    "image/bmp",
}

EXTENSION_CONTENT_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
}


def validate_file_type(file_content_type: Optional[str], filename: Optional[str] = None) -> bool:
    """Validate if file type is supported."""
    if file_content_type and file_content_type in ALLOWED_CONTENT_TYPES:
        return True

    if filename:
        ext = Path(filename).suffix.lower()
        inferred = EXTENSION_CONTENT_TYPES.get(ext)
        return inferred in ALLOWED_CONTENT_TYPES if inferred else False

    return False


def ensure_upload_directory(path: Path) -> None:
    """Ensure upload directories exist."""
    path.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """Prevent directory traversal by stripping path separators."""
    return os.path.basename(filename)


async def save_uploaded_file(
    upload_file: UploadFile,
    *,
    clinic_id: str,
    upload_id: str,
) -> Tuple[str, int]:
    """Save uploaded file and return file path + size."""
    try:
        filename = sanitize_filename(upload_file.filename or "upload.bin")
        upload_dir = Path("uploads") / clinic_id / upload_id
        ensure_upload_directory(upload_dir)
        file_path = upload_dir / filename

        contents = await upload_file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(contents)

        return str(file_path), len(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


def get_file_info(file_path: str) -> dict:
    """Get file information."""
    try:
        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
        }
    except Exception:
        return {"size": 0, "created": None, "modified": None}
