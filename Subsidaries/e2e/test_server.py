import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import proposal_ai
import server
from multimodal import OCRResult


if not shutil.which("tesseract"):
    test_ocr_text = (
        "PUDUCHERRY POLICE\n"
        "PATROL VEHICLE REQUIREMENT\n"
        "Procurement of patrol cars for North Zone.\n"
        "Replace aging police patrol vehicles. Current maintenance costs are rising.\n"
        "Eight GPS equipped police patrol SUVs with emergency lights are requested.\n"
        "Estimated cost: 12000000 rupees. Improve night and highway response coverage."
    )

    def use_test_ocr(filename, file_bytes):
        if not file_bytes:
            return OCRResult(error="The uploaded test scan was empty.")
        return OCRResult(text=test_ocr_text, page_texts=[test_ocr_text], confidence=0.99)

    proposal_ai.ocr_any = use_test_ocr
    print("[E2E] Tesseract is unavailable; using a deterministic OCR fixture for browser coverage.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server.app.run(host="127.0.0.1", port=port, debug=False)