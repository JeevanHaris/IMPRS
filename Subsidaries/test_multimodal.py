import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from multimodal import ocr_any
from proposal_ai import create_draft_from_scan


class MultimodalOcrTests(unittest.TestCase):
    def test_image_ocr_uses_tesseract_without_ollama(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (16, 12), "white").save(image_buffer, format="JPEG")
        tesseract = SimpleNamespace(
            pytesseract=SimpleNamespace(tesseract_cmd="tesseract"),
            image_to_string=Mock(return_value="PUDUCHERRY POLICE"),
            image_to_data=Mock(return_value={"conf": ["92", "-1"]}),
            Output=SimpleNamespace(DICT="dict"),
        )

        with patch.dict(sys.modules, {"pytesseract": tesseract}):
            result = ocr_any("notice.jpg", image_buffer.getvalue())

        self.assertTrue(result.success)
        self.assertEqual(result.text, "PUDUCHERRY POLICE")
        self.assertEqual(result.ocr_engine, "tesseract")
        self.assertEqual(result.confidence, 0.92)
        tesseract.image_to_string.assert_called_once()

    def test_pdf_ocr_renders_with_pymupdf_without_poppler(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (16, 12), "white").save(image_buffer, format="PNG")
        pixmap = SimpleNamespace(tobytes=Mock(return_value=image_buffer.getvalue()))
        page = SimpleNamespace(get_pixmap=Mock(return_value=pixmap))

        class FakePdf:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return iter([page])

        fitz = SimpleNamespace(open=Mock(return_value=FakePdf()), Matrix=Mock(return_value="matrix"))
        tesseract = SimpleNamespace(
            pytesseract=SimpleNamespace(tesseract_cmd="tesseract"),
            image_to_string=Mock(return_value="SCANNED POLICE REPORT"),
            image_to_data=Mock(return_value={"conf": ["88", "-1"]}),
            Output=SimpleNamespace(DICT="dict"),
        )

        with patch.dict(sys.modules, {"fitz": fitz, "pytesseract": tesseract}):
            result = ocr_any("scan.pdf", b"pdf-bytes")

        self.assertTrue(result.success)
        self.assertEqual(result.text, "SCANNED POLICE REPORT")
        self.assertEqual(result.ocr_engine, "tesseract")
        fitz.open.assert_called_once_with(stream=b"pdf-bytes", filetype="pdf")
        page.get_pixmap.assert_called_once()

    def test_scan_draft_extracts_fields_for_proposal_form(self):
        ocr_result = SimpleNamespace(success=True, text="Patrol vehicles needed for North Zone", confidence=0.91, error=None)
        gateway = Mock()
        gateway.call.return_value = SimpleNamespace(content=(
            '{"title":"North Zone patrol vehicles","category":"Procurement",'
            '"department":"Law and Order (North)","description":"Replace aging patrol cars.",'
            '"justification":"Maintenance costs are rising.","estimated_cost":12000000,"priority":"High"}'
        ))

        with unittest.mock.patch("proposal_ai.ocr_any", return_value=ocr_result):
            result = create_draft_from_scan("request.png", b"scan", gateway, "llama3.2")

        self.assertTrue(result["ai_drafted"])
        self.assertEqual(result["ocr_confidence"], 0.91)
        self.assertEqual(result["draft"]["title"], "North Zone patrol vehicles")
        self.assertEqual(result["draft"]["estimated_cost"], 12000000)
        self.assertEqual(result["draft"]["priority"], "High")


if __name__ == "__main__":
    unittest.main()