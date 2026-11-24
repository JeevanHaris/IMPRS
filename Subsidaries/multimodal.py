"""
IPMPRS — Multimodal OCR Engine
────────────────────────────────────────────────────────────────────────
Handles image OCR and scanned-PDF OCR via pytesseract (Tesseract), with
PyMuPDF used to render scanned PDF pages.

Returns structured OCRResult objects consumed by ingestion.py.
"""

import os
import io
import shutil
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


def _configure_tesseract(pytesseract):
    configured_path = os.environ.get("TESSERACT_CMD")
    if configured_path:
        pytesseract.pytesseract.tesseract_cmd = configured_path
        return

    if os.name == "nt" and shutil.which("tesseract") is None:
        candidates = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        )
        for candidate in candidates:
            if os.path.isfile(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                return


# ─── Image OCR ───────────────────────────────────────────────────────

def ocr_image(file_bytes: bytes, gateway=None, vision_model=None) -> OCRResult:
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
        _configure_tesseract(pytesseract)
    except ImportError as e:
        return OCRResult(error=f"Image OCR dependencies missing: {e}. Run: pip install pytesseract Pillow")

    try:
        image = Image.open(io.BytesIO(file_bytes))
        processed = _preprocess_image(image)
        text = pytesseract.image_to_string(processed, config=r"--oem 3 --psm 6", lang="eng").strip()
        if not text:
            return OCRResult(error="Tesseract did not detect readable text in the image.")

        confidence = 0.0
        try:
            data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
            confidence_values = [float(value) for value in data["conf"] if float(value) >= 0]
            if confidence_values:
                confidence = sum(confidence_values) / len(confidence_values) / 100.0
        except Exception:
            pass

        return OCRResult(
            text=text,
            page_texts=[text],
            confidence=round(confidence, 2),
            ocr_engine="tesseract",
        )
    except Exception as e:
        return OCRResult(error=f"Tesseract image OCR failed: {e}. Ensure Tesseract is installed and on PATH.")


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
        import fitz
        import pytesseract
        from PIL import Image
        _configure_tesseract(pytesseract)
    except ImportError as e:
        return OCRResult(error=f"OCR dependencies missing: {e}. Run: pip install PyMuPDF pytesseract Pillow")

    try:
        scale = dpi / 72
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
            images = [
                Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(scale, scale)).tobytes("png"))).copy()
                for page in pdf
            ]
    except Exception as e:
        return OCRResult(error=f"PDF render error: {e}")

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
                conf_values = [float(value) for value in data["conf"] if float(value) >= 0]
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
        return OCRResult(error="OCR produced no text — ensure Tesseract is installed and available on PATH")

    return OCRResult(
        text=full_text,
        page_texts=page_texts,
        confidence=round(avg_conf, 2),
        ocr_engine="tesseract",
    )


# ─── Standalone OCR endpoint helper ──────────────────────────────────

def ocr_any(filename: str, file_bytes: bytes, gateway=None, vision_model=None) -> OCRResult:
    """
    Auto-detect file type and run the appropriate OCR pipeline.
    Used by the /api/ocr endpoint.
    """
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    image_exts = {"png", "jpg", "jpeg", "bmp", "tiff", "tif", "gif", "webp"}
    pdf_exts = {"pdf"}

    if ext in image_exts:
        return ocr_image(file_bytes, gateway=gateway, vision_model=vision_model)
    elif ext in pdf_exts:
        return ocr_pdf(file_bytes)
    else:
        return OCRResult(error=f"Unsupported file type for OCR: .{ext}. Supported: PDF, PNG, JPG, BMP, TIFF, WEBP")
