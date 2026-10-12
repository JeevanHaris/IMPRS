import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image

from multimodal import ocr_any


class MultimodalOcrTests(unittest.TestCase):
    def test_image_ocr_uses_ollama_vision_without_tesseract(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (16, 12), "white").save(image_buffer, format="JPEG")
        gateway = Mock()
        gateway.call.return_value = SimpleNamespace(content="PUDUCHERRY POLICE")

        result = ocr_any("notice.jpg", image_buffer.getvalue(), gateway=gateway, vision_model="llama3.2-vision:11b")

        self.assertTrue(result.success)
        self.assertEqual(result.text, "PUDUCHERRY POLICE")
        self.assertEqual(result.ocr_engine, "llama3.2-vision:11b")
        model, messages = gateway.call.call_args.args
        self.assertEqual(model, "llama3.2-vision:11b")
        self.assertIn("images", messages[1])
        self.assertTrue(messages[1]["images"][0].startswith(b"\x89PNG"))
        self.assertNotIn("timeout", gateway.call.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()