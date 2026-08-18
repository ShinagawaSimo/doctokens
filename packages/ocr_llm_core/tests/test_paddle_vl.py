"""Contract tests for PaddleVLProvider — no network calls."""

from __future__ import annotations

import json
import unittest
import urllib.parse
from unittest.mock import MagicMock, patch

from ocr_llm_core._paddle_vl import PaddleVLProvider, _image_dimensions, _object_mapping, _parse_json_object

PNG_BYTES = b"\x89PNG\r\n\x1a\nvalid-enough-for-adapter"


def _response(payload: object) -> MagicMock:
    mock_response = MagicMock()
    if isinstance(payload, bytes):
        mock_response.read.return_value = payload
    else:
        mock_response.read.return_value = json.dumps(payload).encode()
    mock_response.__enter__.return_value = mock_response
    return mock_response


class PaddleVLProviderTest(unittest.TestCase):
    def test_implements_ocr_provider(self) -> None:
        from ocr_llm_core._provider import OcrProvider

        self.assertIsInstance(PaddleVLProvider("k", "s"), OcrProvider)

    def test_defaults(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        self.assertEqual(p.api_key, "key1")
        self.assertEqual(p.secret_key, "secret1")
        self.assertEqual(p.language, "cht")
        self.assertEqual(p.poll_interval, 5.0)
        self.assertEqual(p.timeout, 120)
        self.assertFalse(p.error_on_empty)

    def test_extract_returns_markdown_on_success(self) -> None:
        """Simulate full submit→poll→download flow."""
        p = PaddleVLProvider("k", "s")
        expected = "## Title\n\nParagraph text\n\n| A | B |\n|---|---|\n| 1 | 2 |"

        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", return_value="task-abc"),
            patch.object(p, "_poll", return_value=("success", None, {"markdown_url": "https://x.bcebos.com/a.md"})),
            patch.object(p, "_download_markdown", return_value=expected),
        ):
            result = p.extract(PNG_BYTES)
        self.assertEqual(result, expected)

    def test_extract_returns_empty_on_api_failure(self) -> None:
        p = PaddleVLProvider("k", "s")
        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", side_effect=RuntimeError("network down")),
        ):
            result = p.extract(PNG_BYTES)
        self.assertEqual(result, "")

    def test_extract_returns_empty_on_poll_timeout(self) -> None:
        p = PaddleVLProvider("k", "s", timeout=0.1, poll_interval=0.05)
        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", return_value="task-abc"),
            patch.object(p, "_poll", return_value=("timeout", "timed out", {})),
        ):
            result = p.extract(PNG_BYTES)
        self.assertEqual(result, "")

    def test_error_on_empty_false_returns_empty_for_empty_result(self) -> None:
        p = PaddleVLProvider("k", "s", error_on_empty=False)
        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", return_value="task-abc"),
            patch.object(p, "_poll", return_value=("success", None, {})),
            patch.object(p, "_download_markdown", return_value=""),
        ):
            result = p.extract(PNG_BYTES)
        self.assertEqual(result, "")

    def test_get_access_token_request(self) -> None:
        """Verify token request is well-formed."""
        p = PaddleVLProvider("key1", "secret1")
        mock_response = _response(
            {
                "access_token": "tok-123",
                "expires_in": 2592000,
            }
        )
        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            token = p._get_access_token()
        self.assertEqual(token, "tok-123")
        call_args = mock_urlopen.call_args[0][0]
        body = call_args.data
        self.assertIn(b"client_id=key1", body)
        self.assertIn(b"client_secret=secret1", body)

    def test_json_response_guards(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_json_object(b"[]")
        self.assertEqual(_object_mapping("not-a-map"), {})

    def test_get_access_token_requires_token_field(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        with (
            patch("urllib.request.urlopen", return_value=_response({})),
            self.assertRaises(RuntimeError),
        ):
            p._get_access_token()

    def test_submit_success_and_api_error(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        with patch(
            "urllib.request.urlopen",
            return_value=_response({"error_code": 0, "result": {"task_id": "task-1"}}),
        ) as mock_urlopen:
            task_id = p._submit("tok", PNG_BYTES)

        self.assertEqual(task_id, "task-1")
        request = mock_urlopen.call_args[0][0]
        payload = urllib.parse.parse_qs(request.data.decode())
        self.assertEqual(payload["file_name"], ["image.png"])
        self.assertIn("file_data", payload)

        with (
            patch(
                "urllib.request.urlopen",
                return_value=_response({"error_code": 17, "error_msg": "bad request"}),
            ),
            self.assertRaises(RuntimeError),
        ):
            p._submit("tok", PNG_BYTES)

    def test_poll_success_and_api_error(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        with patch(
            "urllib.request.urlopen",
            return_value=_response({"error_code": 0, "result": {"status": "success"}}),
        ):
            self.assertEqual(p._poll("tok", "task-1"), ("success", None, {"status": "success"}))

        with patch(
            "urllib.request.urlopen",
            return_value=_response({"error_code": 2, "error_msg": "quota"}),
        ):
            self.assertEqual(p._poll("tok", "task-1"), ("failed", "quota", {}))

    def test_download_markdown_success_and_empty(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        with patch(
            "urllib.request.urlopen",
            return_value=_response({"result": {"markdown_url": ""}}),
        ):
            self.assertEqual(p._download_markdown("tok", "task-1"), "")

        opener = MagicMock()
        opener.open.return_value = _response(b"# Parsed")
        with (
            patch(
                "urllib.request.urlopen",
                return_value=_response({"result": {"markdown_url": "https://bucket.bcebos.com/doc.md"}}),
            ),
            patch("urllib.request.build_opener", return_value=opener),
        ):
            self.assertEqual(p._download_markdown("tok", "task-1"), "# Parsed")

    def test_rejects_unsupported_and_oversize_images_locally(self) -> None:
        provider = PaddleVLProvider("key1", "secret1", max_input_bytes=16)
        self.assertEqual(provider.extract_result(b"not-an-image").error_code, "unsupported_image")
        self.assertEqual(provider.extract_result(PNG_BYTES).error_code, "input_too_large")

    def test_constructor_enforces_cloud_image_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "10 MiB"):
            PaddleVLProvider("key1", "secret1", max_input_bytes=11 * 1024 * 1024)

    def test_constructor_rejects_boolean_numeric_options(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout"):
            PaddleVLProvider("key1", "secret1", timeout=True)
        with self.assertRaisesRegex(ValueError, "max_input_bytes"):
            PaddleVLProvider("key1", "secret1", max_input_bytes=True)
        with self.assertRaisesRegex(TypeError, "error_on_empty"):
            PaddleVLProvider("key1", "secret1", error_on_empty=1)  # type: ignore[arg-type]

    def test_rejects_image_over_cloud_edge_limit(self) -> None:
        png_header = PNG_BYTES[:8] + b"\x00\x00\x00\rIHDR" + (8193).to_bytes(4, "big") + (1).to_bytes(4, "big")
        result = PaddleVLProvider("key1", "secret1").extract_result(png_header)
        self.assertEqual(result.error_code, "image_too_large")

    def test_reads_dimensions_from_supported_image_headers(self) -> None:
        jpeg = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x02\x00\x03\x01\x01\x11\x00"
        bmp = bytearray(26)
        bmp[:2] = b"BM"
        bmp[14:18] = (40).to_bytes(4, "little")
        bmp[18:22] = (3).to_bytes(4, "little", signed=True)
        bmp[22:26] = (2).to_bytes(4, "little", signed=True)
        tiff = (
            b"II*\x00\x08\x00\x00\x00\x02\x00"
            b"\x00\x01\x04\x00\x01\x00\x00\x00\x03\x00\x00\x00"
            b"\x01\x01\x04\x00\x01\x00\x00\x00\x02\x00\x00\x00"
        )
        self.assertEqual(_image_dimensions(jpeg, "jpg"), (3, 2))
        self.assertEqual(_image_dimensions(bytes(bmp), "bmp"), (3, 2))
        self.assertEqual(_image_dimensions(tiff, "tiff"), (3, 2))


if __name__ == "__main__":
    unittest.main()
