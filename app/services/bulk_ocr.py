# app/services/bulk_ocr.py
import io
import re
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List

import cv2
import numpy as np
import pytesseract
from PIL import Image
import logging

from app.services.ocr import extract_text_confidence

app_logger = logging.getLogger("reconomed.app")


@dataclass
class BulkOCRResult:
    ocr_text: str
    confidence_score: int
    metadata: Dict[str, Any]


class RomanianBulkOCR:
    """
    v1 Bulk OCR only:
    - image normalization
    - preprocessing
    - multi-config tesseract
    - reconstruct by lines
    - cleanup + spacing repair
    No templates. No layout detection. No ID routing.
    """

    def process(self, image_input, hint_document_type: Optional[str] = None) -> BulkOCRResult:
        image = self._normalize_input_to_image(image_input)
        text, conf, meta = self._extract_text_romanian_multi(image)
        return BulkOCRResult(ocr_text=text, confidence_score=conf, metadata=meta)

    def _normalize_input_to_image(self, image_input) -> Image.Image:
        if isinstance(image_input, bytes):
            image = Image.open(io.BytesIO(image_input))
            image.load()
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            return image
        if isinstance(image_input, Image.Image):
            img_copy = image_input.copy()
            if img_copy.mode not in ("RGB", "L"):
                img_copy = img_copy.convert("RGB")
            return img_copy
        raise TypeError(f"Unsupported input type: {type(image_input)}")

    def _preprocess_for_document(self, pil_img: Image.Image) -> Image.Image:
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.fastNlMeansDenoising(gray, h=12)
        thr = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 11
        )
        return Image.fromarray(thr)

    def _preprocess_grayscale_clahe(self, pil_img: Image.Image) -> Image.Image:
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # local contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # mild denoise
        gray = cv2.fastNlMeansDenoising(gray, h=10)

        return Image.fromarray(gray)

    def _reconstruct_text_by_lines(self, ocr_data: dict) -> str:
        words = []
        n = len(ocr_data.get("text", []))
        for i in range(n):
            txt = (ocr_data["text"][i] or "").strip()
            conf = ocr_data["conf"][i]
            if not txt:
                continue
            try:
                if float(conf) < 0:
                    continue
            except Exception:
                pass
            words.append({
                "block": ocr_data["block_num"][i],
                "par": ocr_data["par_num"][i],
                "line": ocr_data["line_num"][i],
                "left": ocr_data["left"][i],
                "text": txt
            })

        from collections import defaultdict
        lines = defaultdict(list)
        for w in words:
            lines[(w["block"], w["par"], w["line"])].append(w)

        out_lines = []
        for key in sorted(lines.keys()):
            line_words = sorted(lines[key], key=lambda x: x["left"])
            out_lines.append(" ".join(w["text"] for w in line_words))
        return "\n".join(out_lines)

    def _clean_romanian_ocr_errors(self, text: str) -> str:
        corrections = {
            'Ã£': 'ă', 'Ã¢': 'â', 'Ã®': 'î', 'ÅŸ': 'ș', 'Å£': 'ț',
            r'\bCNF\b': 'CNP',
            r'(\d)\s+(\d)': r'\1\2',
            r'([A-ZĂÂÎȘȚ])\s+([a-zăâîșț])': r'\1\2',
        }
        cleaned = text
        for pattern, replacement in corrections.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        return cleaned

    def _repair_spacing(self, text: str) -> str:
        text = re.sub(r"([,;:\.\!\?])(?=\S)", r"\1 ", text)
        text = re.sub(r"([a-zăâîșț])([A-ZĂÂÎȘȚ])", r"\1 \2", text)
        text = re.sub(r"([A-Za-zăâîșțĂÂÎȘȚ])(\d)", r"\1 \2", text)
        text = re.sub(r"(\d)([A-Za-zăâîșțĂÂÎȘȚ])", r"\1 \2", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"[|]{2,}", " ", text)
        text = re.sub(r"^\s*[|/]+\s*$", "", text, flags=re.MULTILINE)

        # split common Romanian glued patterns (very high ROI)
        text = re.sub(r"\b(S-a)([a-zăâîșț])", r"\1 \2", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(Se)(va|a)\b", r"\1 \2", text, flags=re.IGNORECASE)  # "Seva" -> "Se va" (common OCR)
        text = re.sub(r"(Evitarea|Igienizare|Reevaluare|Leziune|Diagnosticul|Tratament|Recomandări)(?=[A-Za-zăâîșț])",
                    r"\1 ", text)

        # remove line-noise characters that survive thresholding
        text = re.sub(r"[|]{1,}", " ", text)
        text = re.sub(r"[_]{1,}", " ", text)
        text = re.sub(r"\s*/\s*", " ", text)

        # collapse whitespace
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _basic_fallback_ocr(self, image: Image.Image) -> Tuple[str, int]:
        try:
            result = extract_text_confidence(image)
            return result["full_text"], result["average_confidence"]
        except Exception as e:
            app_logger.error(f"Fallback OCR failed: {e}", exc_info=True)
            return f"OCR processing failed: {str(e)}", 0

    def _extract_text_romanian_multi(self, image: Image.Image) -> Tuple[str, int, Dict[str, Any]]:
        """
        Multi-config OCR. Returns (best_text, best_conf, metadata).
        """
        try:
            orig=image

            variants = [
                ("thr", self._preprocess_for_document(orig)),
                ("clahe", self._preprocess_grayscale_clahe(orig)),
            ]

            ocr_configs = [
                ("psm3", r"--oem 3 --psm 3 -c preserve_interword_spaces=1"),
                ("psm4", r"--oem 3 --psm 4 -c preserve_interword_spaces=1"),
                ("psm6", r"--oem 3 --psm 6 -c preserve_interword_spaces=1"),
                ("psm11", r"--oem 3 --psm 11 -c preserve_interword_spaces=1"),
            ]

            best_text, best_conf, best_score, best_tag = "", 0, float("-inf"), None

            for variant_tag, variant_img in variants:
                # Use variant_img for OCR in this iteration
                for config_tag, config in ocr_configs:
                    ocr_data = pytesseract.image_to_data(
                        variant_img, lang="ron+eng", config=config,
                        output_type=pytesseract.Output.DICT
                    )

                    raw = self._reconstruct_text_by_lines(ocr_data)
                    cleaned = self._repair_spacing(self._clean_romanian_ocr_errors(raw))

                    confs = []
                    for c in ocr_data.get("conf", []):
                        if c == "-1":
                            continue
                        try:
                            confs.append(int(float(c)))
                        except Exception:
                            continue
                    avg_conf = int(sum(confs) / len(confs)) if confs else 0

                    tokens = cleaned.split()
                    word_count = len(tokens)
                    garbage_ratio = (sum(1 for w in tokens if len(w) <= 1) / word_count) if word_count else 1.0
                    long_ratio = (sum(1 for t in tokens if len(t) >= 20) / word_count) if word_count else 1.0

                    score = avg_conf + 0.3 * word_count - 20 * garbage_ratio - 25 * long_ratio

                    if score > best_score and cleaned.strip():
                        best_score, best_text, best_conf, best_tag = score, cleaned, avg_conf, tag

            return best_text, best_conf, {"method": "bulk_ocr", "best_config": best_tag}

        except Exception as e:
            app_logger.error(f"Romanian OCR failed: {e}", exc_info=True)
            text, conf = self._basic_fallback_ocr(image)
            return text, conf, {"method": "fallback"}
