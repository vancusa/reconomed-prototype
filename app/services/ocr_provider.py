"""OCR provider interfaces and implementations."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Dict

from openai import OpenAI

from app.utils.file import (
    extract_pdf_text_fast,
    normalize_mime_type,
    rasterize_pdf_to_images,
)


OCR_SYSTEM_PROMPT = (
    "Ești un motor OCR medical. Extrage fidel tot textul vizibil din document, "
    "păstrând diacriticele românești și ordinea aproximativă. "
    "Nu interpreta, nu rezuma, nu adăuga informații."
)


@dataclass
class OCRResult:
    text: str
    metadata: Dict[str, str]


class OCRProvider:
    def extract_text(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        raise NotImplementedError


class OpenAIOCRProvider(OCRProvider):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI OCR.")
        self.client = OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_OCR_MODEL", "gpt-4o-mini")

    def extract_text(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        normalized = normalize_mime_type(file_bytes, content_type=mime_type)

        if normalized == "application/pdf":
            return self._extract_from_pdf(file_bytes)

        return self._extract_from_image(file_bytes, normalized)

    def _extract_from_pdf(self, file_bytes: bytes) -> OCRResult:
        text, metadata = extract_pdf_text_fast(file_bytes)
        if text:
            return OCRResult(text=text, metadata=metadata)

        page_images, raster_meta = rasterize_pdf_to_images(file_bytes)
        pages_text = []
        for index, page_bytes in enumerate(page_images, start=1):
            page_text = self._extract_from_image(page_bytes, "image/png").text
            pages_text.append(f"\n\n--- Page {index} ---\n\n{page_text}".strip())

        merged = "\n".join(pages_text).strip()
        combined_meta = {"method": "openai_vision_pdf", **raster_meta}
        return OCRResult(text=merged, metadata=combined_meta)

    def _extract_from_image(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        image_url = f"data:{mime_type};base64,{encoded}"

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extrage tot textul vizibil."},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        )

        text = response.choices[0].message.content or ""
        return OCRResult(text=text.strip(), metadata={"method": "openai_vision", "model": self.model})