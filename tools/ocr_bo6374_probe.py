"""Read a scanned BO 6374 page as unreviewed Arabic OCR candidates.

This diagnostic never creates an official coverage universe or a publication fact.
Requires PyMuPDF and the pinned Python WinRT OCR bindings on Windows.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import fitz


DEFAULT_SOURCE = Path("data/raw/elections/warehouse/legal/bo_6374_ar_decree_2_15_402_communes_2015.pdf")
EXPECTED_SOURCE_SHA256 = "4bd3823f3ce2fa92c623c48431f7e93e5fb80200628adb184fae7e23b1a23f4d"


def verify_pinned_source(source: Path) -> str:
    observed = hashlib.sha256(source.read_bytes()).hexdigest()
    if observed != EXPECTED_SOURCE_SHA256:
        raise ValueError("BO 6374 source does not match its pinned SHA-256")
    return observed


async def recognize_page(source: Path, page_index: int, scale: float) -> dict:
    if not 1 <= scale <= 3:
        raise ValueError("OCR render scale must be between 1 and 3")
    source_sha256 = verify_pinned_source(source)
    document = fitz.open(source)
    try:
        if not 34 <= page_index <= 65:
            raise ValueError("only the original decree 2.15.402 annex pages (PDF indices 34-65) are admissible")
        if document[page_index].get_text().strip():
            raise ValueError("the original BO annex is expected to be scanned without extractible text")
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage import StorageFile

        with tempfile.TemporaryDirectory(prefix="warehouse_bo6374_ocr_") as temporary:
            image_path = Path(temporary) / "page.png"
            document[page_index].get_pixmap(matrix=fitz.Matrix(scale, scale)).save(image_path)
            rendered_sha256 = hashlib.sha256(image_path.read_bytes()).hexdigest()
            file = await StorageFile.get_file_from_path_async(str(image_path))
            stream = await file.open_read_async()
            try:
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                engine = OcrEngine.try_create_from_language(Language("ar-SA"))
                if engine is None:
                    raise RuntimeError("Windows Arabic OCR language pack ar-SA is unavailable")
                result = await engine.recognize_async(bitmap)
                return {
                    "source": str(source),
                    "source_sha256": source_sha256,
                    "rendered_page_sha256": rendered_sha256,
                    "pdf_page_index": page_index,
                    "printed_page": page_index + 6071,
                    "language": "ar-SA",
                    "scale": scale,
                    "status": "CANDIDATE_OCR_NOT_VERIFIED",
                    "lines": [
                        {
                            "text": line.text,
                            "y": min((word.bounding_rect.y for word in line.words), default=None),
                            "x": min((word.bounding_rect.x for word in line.words), default=None),
                        }
                        for line in result.lines
                    ],
                }
            finally:
                stream.close()
    finally:
        document.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--page-index", type=int, default=34)
    parser.add_argument("--scale", type=float, default=1.5)
    options = parser.parse_args()
    print(json.dumps(asyncio.run(recognize_page(options.source, options.page_index, options.scale)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
