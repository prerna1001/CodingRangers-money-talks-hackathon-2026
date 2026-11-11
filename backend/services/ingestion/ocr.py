from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO


@dataclass
class OcrResult:
    text: str
    confidence: float | None
    warnings: list[str]


def preprocess_image(raw: bytes) -> bytes:
    """Correct common scan defects before a local OCR engine sees the image."""
    try:
        from PIL import Image, ImageEnhance, ImageOps

        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image).convert("L")
        image = ImageEnhance.Contrast(image).enhance(1.5)
        image.thumbnail((2400, 2400))
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
    except ImportError as exc:
        raise RuntimeError("Image OCR requires Pillow. Install the ingestion dependencies.") from exc


def extract_text(raw: bytes) -> OcrResult:
    """Use a locally installed OCR engine; never make a network request."""
    prepared = preprocess_image(raw)
    try:
        import numpy as np
        from paddleocr import PaddleOCR
        from PIL import Image

        engine = PaddleOCR(lang="en")
        image = np.asarray(Image.open(BytesIO(prepared)).convert("RGB"))
        result = engine.predict(input=image, use_doc_orientation_classify=False, use_doc_unwarping=False)
        lines: list[str] = []
        scores: list[float] = []
        for item in result:
            data = item.json if hasattr(item, "json") else item
            data = data.get("res", data) if isinstance(data, dict) else {}
            for text, score in zip(data.get("rec_texts", []), data.get("rec_scores", [])):
                lines.append(str(text))
                scores.append(float(score))
        return OcrResult("\n".join(lines), sum(scores) / len(scores) if scores else None, [])
    except ImportError:
        try:
            import pytesseract
            from PIL import Image

            text = pytesseract.image_to_string(Image.open(BytesIO(prepared)))
            return OcrResult(text, None, ["PaddleOCR unavailable; used local Tesseract fallback without confidence scores."])
        except ImportError as exc:
            raise RuntimeError("No local OCR engine is installed. Install paddleocr or pytesseract.") from exc
