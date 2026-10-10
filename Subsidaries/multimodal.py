"""
IPMPRS — Multimodal OCR Engine
────────────────────────────────────────────────────────────────────────
Handles image and scanned-PDF OCR via:
  1. pytesseract (Tesseract — local, free, robust)
  2. Pillow for image preprocessing (contrast, denoise, upscale)
  3. pdf2image for rendering scanned PDF pages

Returns structured OCRResult objects consumed by ingestion.py.
"""

import os
import io
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Result Types ────────────────────────────────────────────────────

@dataclass
class OCRResult:
    """Result from any OCR operation."""
    text: str = ""
    page_texts: List[str] = field(default_factory=list)
    confidence: float = 0.0
    ocr_engine: str = "tesseract"
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.text.strip())


# ─── Preprocessing Helpers ────────────────────────────────────────────

def _preprocess_image(pil_img):
    """
    Enhance image for better OCR accuracy:
    - Convert to grayscale
    - Increase contrast
    - Slight sharpening
    """
    try:
        from PIL import ImageEnhance, ImageFilter
        img = pil_img.convert("L")  # Grayscale
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        # Upscale small images for better recognition
        w, h = img.size
        if w < 1000:
            scale = 1000 / w
            img = img.resize((int(w * scale), int(h * scale)))
        return img
    except Exception:
        return pil_img


# ─── Image OCR ───────────────────────────────────────────────────────

def ocr_image(file_bytes: bytes) -> OCRResult:
    """
    Run OCR on a single image (PNG, JPG, BMP, TIFF, WEBP, GIF).

    Args:
        file_bytes: Raw image bytes.

    Returns:
        OCRResult with extracted text.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        return OCRResult(error=f"OCR dependencies missing: {e}. Run: pip install pytesseract Pillow")

    try:
        pil_img = Image.open(io.BytesIO(file_bytes))
        pil_img = _preprocess_image(pil_img)

        # Custom Tesseract config: OEM 3 = LSTM, PSM 6 = uniform block of text
        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(pil_img, config=custom_config, lang="eng")

        # Attempt to get confidence
        try:
            data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            conf_values = [c for c in data["conf"] if c != -1]
            avg_conf = sum(conf_values) / len(conf_values) / 100.0 if conf_values else 0.0
        except Exception:
            avg_conf = 0.75  # Default fallback

        return OCRResult(
            text=text.strip(),
            page_texts=[text.strip()],
            confidence=round(avg_conf, 2),
            ocr_engine="tesseract",
        )
    except Exception as e:
        return OCRResult(error=f"Image OCR failed: {e}")


# ─── Scanned PDF OCR ─────────────────────────────────────────────────

def ocr_pdf(file_bytes: bytes, dpi: int = 250) -> OCRResult:
    """
    Render each page of a scanned PDF and run OCR on each image.

    Args:
        file_bytes: Raw PDF bytes.
        dpi:        Rendering resolution (higher = better accuracy, slower).

    Returns:
        OCRResult with per-page texts concatenated.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        return OCRResult(error="pdf2image not installed. Run: pip install pdf2image")

    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        return OCRResult(error=f"OCR dependencies missing: {e}. Run: pip install pytesseract Pillow")

    try:
        images = convert_from_bytes(file_bytes, dpi=dpi)
    except Exception as e:
        return OCRResult(error=f"PDF render error: {e}. Ensure Poppler is installed.")

    page_texts = []
    all_confidences = []

    for i, img in enumerate(images):
        try:
            processed = _preprocess_image(img)
            custom_config = r"--oem 3 --psm 6"
            text = pytesseract.image_to_string(processed, config=custom_config, lang="eng")

            # Confidence
            try:
                data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
                conf_values = [c for c in data["conf"] if c != -1]
                if conf_values:
                    all_confidences.extend(conf_values)
            except Exception:
                pass

            page_texts.append(text.strip())
        except Exception as pe:
            page_texts.append("")  # Failed page → empty
            print(f"[OCR] Page {i+1} error: {pe}")

    full_text = "\n\n".join(pt for pt in page_texts if pt)
    avg_conf = (sum(all_confidences) / len(all_confidences) / 100.0) if all_confidences else 0.75

    if not full_text.strip():
        return OCRResult(error="OCR produced no text — ensure Tesseract and Poppler are installed")

    return OCRResult(
        text=full_text,
        page_texts=page_texts,
        confidence=round(avg_conf, 2),
        ocr_engine="tesseract",
    )


# ─── Standalone OCR endpoint helper ──────────────────────────────────

def ocr_any(filename: str, file_bytes: bytes) -> OCRResult:
    """
    Auto-detect file type and run the appropriate OCR pipeline.
    Used by the /api/ocr endpoint.
    """
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    image_exts = {"png", "jpg", "jpeg", "bmp", "tiff", "tif", "gif", "webp"}
    pdf_exts = {"pdf"}

    if ext in image_exts:
        return ocr_image(file_bytes)
    elif ext in pdf_exts:
        return ocr_pdf(file_bytes)
    else:
        return OCRResult(error=f"Unsupported file type for OCR: .{ext}. Supported: PDF, PNG, JPG, BMP, TIFF, WEBP")
