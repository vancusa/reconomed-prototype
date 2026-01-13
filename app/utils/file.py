"""File handling utilities"""
import io
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image

from fastapi import HTTPException, UploadFile

app_logger = logging.getLogger("reconomed.app")

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

PDF_MAX_PAGES = int(os.getenv("RECONOMED_PDF_MAX_PAGES", "10"))
PDF_MAX_DIMENSION = int(os.getenv("RECONOMED_PDF_MAX_DIMENSION", "1600"))


def normalize_mime_type(file_bytes: bytes, filename: Optional[str] = None, content_type: Optional[str] = None) -> str:
    """Normalize input MIME type using content and filename hints."""
    if content_type and content_type in ALLOWED_CONTENT_TYPES:
        return content_type

    if file_bytes.startswith(b"%PDF"):
        return "application/pdf"

    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if file_bytes.startswith(b"\xff\xd8"):
        return "image/jpeg"

    if filename:
        ext = Path(filename).suffix.lower()
        inferred = EXTENSION_CONTENT_TYPES.get(ext)
        if inferred in ALLOWED_CONTENT_TYPES:
            return inferred

    return "application/octet-stream"


def _is_text_usable(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < 20:
        return False
    alnum = sum(char.isalnum() for char in stripped)
    ratio = alnum / max(len(stripped), 1)
    return ratio > 0.2


def extract_pdf_text_fast(file_bytes: bytes) -> Tuple[str, dict]:
    """Extract selectable text from PDF, if present."""
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        text = "\n".join(page.get_text("text") for page in doc)
        usable = _is_text_usable(text)
        return text if usable else "", {
            "method": "pdf_text_extract",
            "page_count": doc.page_count,
            "usable": usable,
        }


def rasterize_pdf_to_images(file_bytes: bytes, max_pages: int = PDF_MAX_PAGES) -> Tuple[List[bytes], dict]:
    """Rasterize PDF pages to PNG bytes with page and size limits."""
    images: List[bytes] = []
    metadata = {
        "method": "pdf_raster",
        "page_count": 0,
        "max_pages": max_pages,
        "truncated": False,
    }

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = doc.page_count
        metadata["page_count"] = total_pages
        if total_pages > max_pages:
            metadata["truncated"] = True
            app_logger.warning(
                "PDF exceeds max pages (%s). Truncating from %s pages.",
                max_pages,
                total_pages,
            )

        for page_index in range(min(total_pages, max_pages)):
            page = doc.load_page(page_index)
            rect = page.rect
            scale = min(1.0, PDF_MAX_DIMENSION / max(rect.width, rect.height))
            matrix = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            if max(image.size) > PDF_MAX_DIMENSION:
                resize_scale = PDF_MAX_DIMENSION / max(image.size)
                image = image.resize(
                    (int(image.size[0] * resize_scale), int(image.size[1] * resize_scale)),
                    Image.LANCZOS,
                )

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            images.append(buffer.getvalue())

    metadata["rasterized_pages"] = len(images)
    return images, metadata


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
