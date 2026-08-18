"""Provider-neutral OCR result and batching contracts."""

from __future__ import annotations

import threading
import unittest

from ocr_llm_core import OcrProvider, OcrResult, OcrStatus, run_ocr_batch


class _CountingProvider(OcrProvider):
    max_concurrency = 2

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def extract(self, image_bytes: bytes) -> str:
        with self._lock:
            self.calls += 1
        return image_bytes.decode()


class OcrResultTests(unittest.TestCase):
    def test_from_text_distinguishes_success_and_empty(self) -> None:
        self.assertEqual(OcrResult.from_text(" text ").status, OcrStatus.SUCCESS)
        self.assertEqual(OcrResult.from_text(" \n ").status, OcrStatus.EMPTY)
        self.assertEqual(OcrResult.from_text(None).error_code, "invalid_result")

    def test_result_invariants_reject_contradictions(self) -> None:
        with self.assertRaises(ValueError):
            OcrResult(OcrStatus.SUCCESS, "text", error_code="bad")
        with self.assertRaises(ValueError):
            OcrResult(OcrStatus.EMPTY, error_code="bad")
        with self.assertRaises(ValueError):
            OcrResult(OcrStatus.ERROR, text="text", error_code="bad")


class BatchTests(unittest.TestCase):
    def test_deduplicates_equal_image_bytes(self) -> None:
        provider = _CountingProvider()
        result = run_ocr_batch({"img1": b"same", "img2": b"same", "img3": b"other"}, provider)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(result["img1"], result["img2"])
        self.assertEqual(result["img3"].text, "other")

    def test_accepts_extract_result_only_duck_provider(self) -> None:
        class DuckProvider:
            max_concurrency = 1

            def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> dict[str, str]:
                return {"status": "success", "text": image_bytes.decode()}

        result = run_ocr_batch({"img1": b"duck"}, DuckProvider())
        self.assertEqual(result["img1"].text, "duck")

    def test_invalid_structured_result_is_not_treated_as_empty(self) -> None:
        class BadProvider:
            def extract_result(self, image_bytes: bytes) -> dict[str, str]:
                return {"status": "success", "text": ""}

        result = run_ocr_batch({"img1": b"x"}, BadProvider())
        self.assertEqual(result["img1"].error_code, "invalid_result")

    def test_rejects_contradictory_structured_results(self) -> None:
        class BadProvider:
            max_concurrency = 3

            def __init__(self) -> None:
                self.call = 0

            def extract_result(self, image_bytes: bytes) -> dict[str, str]:
                self.call += 1
                if self.call == 1:
                    return {"status": "success", "text": "text", "error_code": "also-error"}
                if self.call == 2:
                    return {"status": "empty", "text": "", "error_message": "also-error"}
                return {"status": "error", "text": "text", "error_code": "engine_error"}

        results = run_ocr_batch({"one": b"1", "two": b"2", "three": b"3"}, BadProvider(), max_workers=1)
        self.assertTrue(all(result.error_code == "invalid_result" for result in results.values()))

    def test_rejects_non_finite_timeout_and_non_integer_workers(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout"):
            run_ocr_batch({}, _CountingProvider(), timeout=float("nan"))
        with self.assertRaisesRegex(ValueError, "timeout"):
            run_ocr_batch({}, _CountingProvider(), timeout=True)
        with self.assertRaisesRegex(ValueError, "max_workers"):
            run_ocr_batch({}, _CountingProvider(), max_workers=1.5)  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "string keys"):
            run_ocr_batch({1: b"image"}, _CountingProvider())  # type: ignore[dict-item]


if __name__ == "__main__":
    unittest.main()
