# app/services/document.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging

from app.services.ocr_provider import OpenAIOCRProvider
from app.utils.file import normalize_mime_type

app_logger = logging.getLogger("reconomed.app")


@dataclass
class DocumentProcessingResult:
    """
    v1 contract: Bulk OCR only. No templates, no document classification,
    no ID-card logic, no lab interpretation.

    Keep keys stable so routers/workers stay simple.
    """
    success: bool
    ocr_text: str
    confidence_score: int
    document_type: Optional[str]
    structured_data: Dict[str, Any]
    processing_metadata: Dict[str, Any]
    error: Optional[str] = None


class DocumentService:
    """
    v1 Document service:
    - Runs OCR via OpenAI Vision for images and PDFs.
    - Returns OCR text + confidence + minimal metadata.
    - Leaves document_type empty (or passes through hint, but does not infer).
    - structured_data is always {} in v1.
    """

    def __init__(self) -> None:
        self.ocr = OpenAIOCRProvider()

    def process_document_bulk(
        self,
        file_content: bytes,
        hint_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Primary entry point for v1 OCR.
        `file_content` should be bytes of an image (or already-rasterized PDF page bytes).

        Returns a dict so the rest of the codebase can serialize easily.
        """
        try:
            # DO NOT log OCR text or file content (PHI). Keep logs metadata-only.
            app_logger.debug("DocumentService: starting OCR")
            mime_type = normalize_mime_type(file_content)
            result = self.ocr.extract_text(file_content, mime_type)

            payload = DocumentProcessingResult(
                success=True,
                ocr_text=(result.text or ""),
                confidence_score=0,
                # v1: no classification; we optionally echo hint for convenience
                document_type=hint_type,
                structured_data={},  # v1 by design
                processing_metadata=(result.metadata or {"method": "openai_ocr"}),
                error=None,
            )
            return payload.__dict__

        except Exception as e:
            # Log exception safely; no PHI.
            app_logger.error("DocumentService: OCR failed", exc_info=True)

            payload = DocumentProcessingResult(
                success=False,
                ocr_text="",
                confidence_score=0,
                document_type=hint_type,
                structured_data={},
                processing_metadata={"method": "openai_ocr"},
                error=str(e),
            )
            return payload.__dict__

    # Optional compatibility alias: if older code calls this name, keep it working.
    def process_document_with_templates(
        self,
        file_content: bytes,
        hint_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Backwards-compatible alias for older callers.
        Despite the name, v1 does NOT do templates.
        """
        return self.process_document_bulk(file_content=file_content, hint_type=hint_type)
