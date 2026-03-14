#!/usr/bin/env python3
"""
Bulk OCR test harness (CLI)

Usage:
  python temp_to_test.py path/to/image.jpg

Outputs:
  - Prints a compact scoreboard for each (variant × psm)
  - Writes the best result to out.txt
  - Writes every candidate to out_<variant>_<psm>.txt (for side-by-side diff)

v1 improvements:
  - Add padding border
  - Deskew clamp + cleaner angle mask
  - Hard "symbol soup" candidate rejection
  - Optional conservative lexicon correction (off by default)
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np
import pytesseract
from PIL import Image


# ----------------------------
# Tunables (v1)
# ----------------------------
BORDER_PX = 40

DESKEW_MIN_DEG = 0.6
DESKEW_MAX_DEG = 9.0  # clamp; prevents catastrophic rotations

# Hard rejection thresholds (symbol soup)
MAX_GARBAGE_RATIO = 0.35         # <= 1-char token ratio
MIN_AVG_WORD_LEN = 2.2
MAX_LONG_RATIO = 0.25            # >=16 char tokens ratio
MAX_NON_TEXT_CHAR_RATIO = 0.38   # too many weird chars

# Optional lexicon correction (very conservative)
USE_LEXICON = True
LEXICON_CUTOFF = 0.90  # difflib similarity cutoff (higher = more conservative)


# ----------------------------
# Utility: load image
# ----------------------------
def load_pil(path: Path) -> Image.Image:
    img = Image.open(path)
    img.load()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def add_white_border(pil_img: Image.Image, px: int = BORDER_PX) -> Image.Image:
    """Add a constant white border around the image (helps OCR near edges)."""
    arr = np.array(pil_img)
    if arr.ndim == 2:
        bordered = cv2.copyMakeBorder(arr, px, px, px, px, borderType=cv2.BORDER_CONSTANT, value=255)
        return Image.fromarray(bordered)
    # RGB
    bordered = cv2.copyMakeBorder(arr, px, px, px, px, borderType=cv2.BORDER_CONSTANT, value=(255, 255, 255))
    return Image.fromarray(bordered)


# ----------------------------
# Preprocessing variants
# ----------------------------
def preprocess_threshold(pil_img: Image.Image) -> Image.Image:
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR) if pil_img.mode != "L" else cv2.cvtColor(
        np.array(pil_img), cv2.COLOR_GRAY2BGR
    )
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=12)
    thr = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 11
    )
    return Image.fromarray(thr)


def preprocess_gray(pil_img: Image.Image) -> Image.Image:
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR) if pil_img.mode != "L" else cv2.cvtColor(
        np.array(pil_img), cv2.COLOR_GRAY2BGR
    )
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return Image.fromarray(gray)


def _angle_mask_for_deskew(gray_u8: np.ndarray) -> np.ndarray:
    """
    Build a cleaner foreground mask for angle estimation:
      - Otsu binarize
      - Invert
      - Morph open to drop pepper noise
      - Remove huge blobs (often stamps/logos)
    """
    _, bw = cv2.threshold(gray_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = 255 - bw

    # drop pepper noise
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    inv = cv2.morphologyEx(inv, cv2.MORPH_OPEN, k, iterations=1)

    # remove very large connected components (keep likely text)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    if num_labels <= 1:
        return inv

    h, w = inv.shape[:2]
    max_keep_area = int(0.12 * h * w)  # keep components smaller than 12% page area
    cleaned = np.zeros_like(inv)
    for lab in range(1, num_labels):
        area = stats[lab, cv2.CC_STAT_AREA]
        if 25 <= area <= max_keep_area:
            cleaned[labels == lab] = 255
    return cleaned


def deskew_pil(pil_img: Image.Image) -> Image.Image:
    """
    Deskew with clamp to avoid catastrophic failures.
    Uses a cleaner mask for angle estimation.
    """
    arr = np.array(pil_img)
    if arr.ndim == 3:
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    else:
        gray = arr.copy()

    mask = _angle_mask_for_deskew(gray)
    coords = cv2.findNonZero(mask)
    if coords is None:
        return pil_img

    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    # minAreaRect angle conventions
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < DESKEW_MIN_DEG:
        return pil_img
    if abs(angle) > DESKEW_MAX_DEG:
        # clamp: skip rather than rotating into garbage
        return pil_img

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    rotated = cv2.warpAffine(
        arr,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255) if arr.ndim == 3 else 255
    )
    return Image.fromarray(rotated)


# ----------------------------
# OCR helpers
# ----------------------------
def reconstruct_text_by_lines(ocr_data: Dict[str, Any]) -> str:
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
            "text": txt,
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


def clean_romanian_ocr_errors(text: str) -> str:
    import re
    corrections = {
        "Ã£": "ă", "Ã¢": "â", "Ã®": "î", "ÅŸ": "ș", "Å£": "ț",
        r"\bCNF\b": "CNP",
    }
    out = text
    for pat, rep in corrections.items():
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


def repair_spacing(text: str) -> str:
    import re
    text = re.sub(r"([,;:\.\!\?])(?=\S)", r"\1 ", text)
    text = re.sub(r"([a-zăâîșț])([A-ZĂÂÎȘȚ])", r"\1 \2", text)
    text = re.sub(r"([A-Za-zăâîșțĂÂÎȘȚ])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([A-Za-zăâîșțĂÂÎȘȚ])", r"\1 \2", text)

    text = re.sub(r"\b(S-a)([a-zăâîșț])", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSeva\b", "Se va", text, flags=re.IGNORECASE)

    text = re.sub(r"[|]+", " ", text)
    text = re.sub(r"[_]+", " ", text)
    text = re.sub(r"\s*/\s*", " ", text)

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines).strip()


def avg_confidence_from_data(ocr_data: Dict[str, Any]) -> int:
    confs: List[int] = []
    for c in ocr_data.get("conf", []):
        if c == "-1":
            continue
        try:
            confs.append(int(float(c)))
        except Exception:
            continue
    return int(sum(confs) / len(confs)) if confs else 0


def compute_glue_metrics(text: str) -> Tuple[float, float, float, int, int]:
    tokens = text.split()
    wc = len(tokens)
    cc = len(text)
    if wc == 0:
        return 1.0, 1.0, 999.0, 0, cc

    garbage_ratio = sum(1 for w in tokens if len(w) <= 1) / wc
    long_ratio = sum(1 for w in tokens if len(w) >= 16) / wc
    avg_len = sum(len(w) for w in tokens) / wc
    return garbage_ratio, long_ratio, avg_len, wc, cc


def non_text_char_ratio(text: str) -> float:
    """
    Ratio of characters that are *not* typical Romanian/medical text chars.
    (Conservative; meant for rejecting symbol soup candidates.)
    """
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                  "ăâîșțĂÂÎȘȚ"
                  "0123456789"
                  " \n\t.,;:!?()[]{}<>+-=/%'\"°–—_")
    if not text:
        return 1.0
    bad = sum(1 for ch in text if ch not in allowed)
    return bad / max(1, len(text))


def is_candidate_valid(text: str) -> bool:
    garbR, longR, avgLen, wc, cc = compute_glue_metrics(text)
    if wc == 0 or cc < 30:
        return False
    if garbR > MAX_GARBAGE_RATIO:
        return False
    if longR > MAX_LONG_RATIO:
        return False
    if avgLen < MIN_AVG_WORD_LEN:
        return False
    if non_text_char_ratio(text) > MAX_NON_TEXT_CHAR_RATIO:
        return False
    return True

def score_candidate(conf: int, text: str) -> float:
    """
    Your original idea, plus: invalid candidates get nuked.
    """
    if not is_candidate_valid(text):
        return -1e9

    garbage_ratio, long_ratio, avg_len, wc, cc = compute_glue_metrics(text)
    length_bonus = 0.15 * wc
    avg_len_pen = 1.8 * max(0.0, avg_len - 7.0)

    score = (
        conf
        + length_bonus
        - 18.0 * garbage_ratio
        - 60.0 * long_ratio
        - avg_len_pen
    )

    if cc < 80:
        score -= 15

    return score

def reflow_into_lines(text: str) -> str:
    import re

    # Break after sentence punctuation when next char looks like a new sentence
    text = re.sub(r'([.!?])\s+(?=[A-ZĂÂÎȘȚ])', r'\1\n', text)

    # Break BEFORE multi-word ALL-CAPS headings (not before single tokens)
    # e.g. "PAPILOAME VIRALE MULTIPLE" => stays together
    text = re.sub(
        r'\s+(?=(?:[A-Z0-9ĂÂÎȘȚ]{3,}\s+){1,}[A-Z0-9ĂÂÎȘȚ]{3,}\b)',
        '\n',
        text
    )

    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text

def merge_allcaps_blocks(lines):
    import re
    out = []
    buf = []
    def is_allcaps_line(ln):
        # allow spaces and digits
        return bool(re.fullmatch(r"[A-Z0-9ĂÂÎȘȚ ]{3,}", ln.strip()))

    for ln in lines:
        if is_allcaps_line(ln):
            buf.append(ln.strip())
        else:
            if buf:
                out.append(" ".join(buf))
                buf = []
            out.append(ln)
    if buf:
        out.append(" ".join(buf))
    return out


def drop_truncated_echoes(lines):
    import re
    from difflib import SequenceMatcher

    def norm(ln: str) -> str:
        ln = ln.lower()
        ln = re.sub(r"\s+", " ", ln)
        ln = re.sub(r"[^\wăâîșț]+", " ", ln)
        return re.sub(r"\s+", " ", ln).strip()

    kept = []
    kept_n = []

    for ln in lines:
        n = norm(ln)
        if not n:
            continue

        # If line starts with lowercase and looks like a chopped duplicate, try hard to drop it
        if ln[:1].islower() and kept_n:
            # compare against last 10 kept lines
            for prev in kept_n[-10:]:
                # missing-prefix substring test (1-6 chars)
                for k in (1, 2, 3, 4, 5, 6):
                    if len(n) > k and n[k:] and n[k:] in prev:
                        n = ""
                        break
                if not n:
                    break
        if not n:
            continue

        # Near-duplicate check
        dup = False
        for prev in kept_n[-8:]:
            if SequenceMatcher(None, n, prev).ratio() >= 0.92:
                dup = True
                break
        if dup:
            continue

        kept.append(ln)
        kept_n.append(n)

    return kept


def postprocess_lines(text: str) -> str:
    """
    - Drop junk micro-lines
    - Remove duplicates / near-duplicates
    - Fix common 'missing prefix' duplicates (e.g. 'iuni...' after 'Leziuni...')
    - Merge ALL-CAPS blocks split across lines
    - Light cleanup of weird quote chars
    """
    import re
    from difflib import SequenceMatcher

    text = text.replace("„", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def is_junk_line(ln: str) -> bool:
        if len(ln) <= 2:
            return True
        if re.fullmatch(r"[\W_]+", ln):
            return True
        # 2-token micro-fragment like "A dy" (no digits, too short to be meaningful)
        parts = ln.split()
        if len(parts) == 2 and all(len(p) <= 3 for p in parts) and not any(ch.isdigit() for ch in ln):
            return True
        letters = sum(ch.isalpha() for ch in ln)
        if letters / max(1, len(ln)) < 0.35 and len(ln) < 20:
            return True
        return False

    def is_allcaps_line(ln: str) -> bool:
        # allow digits/spaces; require at least 3 chars to avoid "CO"
        s = ln.strip()
        return len(s) >= 3 and bool(re.fullmatch(r"[A-Z0-9ĂÂÎȘȚ ]+", s)) and any(ch.isalpha() for ch in s)

    def merge_allcaps_blocks(ls):
        merged = []
        buf = []
        for ln in ls:
            if is_allcaps_line(ln):
                buf.append(ln.strip())
            else:
                if buf:
                    merged.append(" ".join(buf))
                    buf = []
                merged.append(ln)
        if buf:
            merged.append(" ".join(buf))
        return merged

    def norm(ln: str) -> str:
        ln = ln.lower()
        ln = re.sub(r"\s+", " ", ln)
        ln = re.sub(r"[^\wăâîșț]+", " ", ln)
        ln = re.sub(r"\s+", " ", ln).strip()
        return ln

    cleaned = [ln for ln in lines if not is_junk_line(ln)]
    cleaned = merge_allcaps_blocks(cleaned)

    out = []
    out_norm = []

    for ln in cleaned:
        n = norm(ln)

        # Drop missing-prefix echoes even if they appear later (common after diagnosis headings)
        if out and ln[:1].islower() and len(n) >= 10:
            for prev_n in out_norm[-12:]:
                for k in (1, 2, 3, 4, 5, 6):
                    if len(n) > k and n[k:] and n[k:] in prev_n:
                        n = ""
                        break
                if not n:
                    break
            if not n:
                continue

        if not n:
            continue

        if out and ln[:1].islower() and len(n) >= 10:
            for prev_n in out_norm[-10:]:  # look back further
                for k in (1, 2, 3, 4, 5, 6):
                    if len(n) > k and n[k:] and n[k:] in prev_n:
                        n = ""
                        break
                if not n:
                    break
            if not n:
                continue

            # keep your original (works well when line boundaries are sane)
            if len(n) >= 10:
                for k in (1, 2, 3, 4):
                    if len(n) > k and n[k:] and n[k:] in prev_n:
                        n = ""
                        break
            if not n:
                continue

        dup = False
        for prev_n in out_norm[-6:]:
            if SequenceMatcher(None, n, prev_n).ratio() >= 0.92:
                dup = True
                break
        if dup:
            continue

        out.append(ln)
        out_norm.append(n)

    return "\n".join(out).strip()



# ----------------------------
# Optional lexicon correction (conservative)
# ----------------------------
def apply_conservative_lexicon(text: str) -> str:
    if not USE_LEXICON:
        return text

    import re
    import difflib

    lexicon = {
        "leziuni", "leziune", "papilomatoase", "multiple", "hiperkeratozica", "pediculata",
        "axilara", "papiloame", "virale", "veruca", "virala", "anestezie", "topica", "crema",
        "lidocaina", "igienizarea", "lantisoarelor", "schimbarea", "lamei", "ras",
        "evitarea", "umezelii", "intemperiilor", "aplica", "cicatrizanta", "vindecarea", "completa",
        "nevoie", "efectuat", "vaporizarea", "leziunilor", "cutanate", "sub",
    }

    def fix_token(tok: str) -> str:
        if len(tok) < 5 or tok.isupper():
            return tok
        if not re.fullmatch(r"[A-Za-zăâîșțĂÂÎȘȚ\-]+", tok):
            return tok

        low = tok.lower()
        if low in lexicon:
            return tok

        cand = difflib.get_close_matches(low, lexicon, n=1, cutoff=LEXICON_CUTOFF)
        if not cand:
            return tok

        repl = cand[0]
        if tok[0].isupper():
            repl = repl.capitalize()
        return repl

    # Preserve newlines: process line by line, token by token
    fixed_lines = []
    for line in text.splitlines():
        toks = line.split()  # keeps intra-line tokenization
        toks = [fix_token(t) for t in toks]
        fixed_lines.append(" ".join(toks))
    return "\n".join(fixed_lines)


@dataclass
class Candidate:
    variant: str
    psm_tag: str
    conf: int
    score: float
    text: str


# ----------------------------
# Main
# ----------------------------
def main():
    if len(sys.argv) != 2:
        print("Usage: python temp_to_test.py <image_path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)

    pil = load_pil(path)

    # v1: padding border first
    pil = add_white_border(pil, px=BORDER_PX)

    # Preprocess variants (include deskewed forms)
    base_thr = preprocess_threshold(pil)
    base_gray = preprocess_gray(pil)

    variants = [
        ("thr", base_thr),
        ("gray", base_gray),
        ("thr_deskew", deskew_pil(base_thr)),
        ("gray_deskew", deskew_pil(base_gray)),
    ]

    ocr_configs = [
        ("psm3", r"--oem 3 --psm 3 -c preserve_interword_spaces=1"),
        ("psm4", r"--oem 3 --psm 4 -c preserve_interword_spaces=1"),
        ("psm6", r"--oem 3 --psm 6 -c preserve_interword_spaces=1"),
        ("psm11", r"--oem 3 --psm 11 -c preserve_interword_spaces=1"),
    ]

    candidates: List[Candidate] = []

    for variant_tag, variant_img in variants:
        for psm_tag, config in ocr_configs:

            ocr_data = pytesseract.image_to_data(
                variant_img,
                lang="ron+eng",
                config=config,
                output_type=pytesseract.Output.DICT
            )

            raw = reconstruct_text_by_lines(ocr_data)
            cleaned = repair_spacing(clean_romanian_ocr_errors(raw))
            cleaned = reflow_into_lines(cleaned)
            cleaned = postprocess_lines(cleaned)
            cleaned = apply_conservative_lexicon(cleaned)

            conf = avg_confidence_from_data(ocr_data)
            sc = score_candidate(conf, cleaned)

            candidates.append(Candidate(
                variant=variant_tag,
                psm_tag=psm_tag,
                conf=conf,
                score=sc,
                text=cleaned
            ))

            out_path = Path(f"out_{variant_tag}_{psm_tag}.txt")
            out_path.write_text(cleaned, encoding="utf-8")

            garbR, longR, avgLen, wc, cc = compute_glue_metrics(cleaned)
            preview = cleaned.replace("\n", " ")[:90]
            ntcr = non_text_char_ratio(cleaned)
            valid_tag = "OK" if is_candidate_valid(cleaned) else "REJ"

            print(
                f"{variant_tag:10s} {psm_tag:5s} {valid_tag:3s} "
                f"conf={conf:2d} score={sc:8.1f} "
                f"wc={wc:3d} avgLen={avgLen:4.1f} longR={longR:4.2f} garbR={garbR:4.2f} nonTxt={ntcr:4.2f} "
                f"| {preview}"
            )

    best = max(candidates, key=lambda c: c.score)

    print("\n=== BEST ===")
    print(f"variant={best.variant} psm={best.psm_tag} conf={best.conf} score={best.score:.1f}")
    print("Wrote best to out.txt\n")

    Path("out.txt").write_text(best.text, encoding="utf-8")
    print(best.text)


if __name__ == "__main__":
    main()
