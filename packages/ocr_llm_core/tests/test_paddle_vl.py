"""Contract tests for PaddleVLProvider — no network calls."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from ocr_llm_core._paddle_vl import PaddleVLProvider


class PaddleVLProviderTest(unittest.TestCase):
    def test_implements_ocr_provider(self) -> None:
        from ocr_llm_core._provider import OcrProvider

        self.assertIsInstance(PaddleVLProvider("k", "s"), OcrProvider)

    def test_defaults(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        self.assertEqual(p.api_key, "key1")
        self.assertEqual(p.secret_key, "secret1")
        self.assertEqual(p.language, "cht")
        self.assertEqual(p.poll_interval, 1.0)
        self.assertEqual(p.timeout, 120)
        self.assertTrue(p.error_on_empty)

    def test_extract_returns_markdown_on_success(self) -> None:
        """Simulate full submit→poll→download flow."""
        p = PaddleVLProvider("k", "s")
        expected = "## Title\n\nParagraph text\n\n| A | B |\n|---|---|\n| 1 | 2 |"

        with patch.object(p, "_get_access_token", return_value="tok"):
            with patch.object(p, "_submit", return_value="task-abc"):
                with patch.object(p, "_poll", return_value=("success", None)):
                    with patch.object(
                        p, "_download_markdown", return_value=expected
                    ):
                        result = p.extract(b"fake-image-bytes")
        self.assertEqual(result, expected)

    def test_extract_returns_empty_on_api_failure(self) -> None:
        p = PaddleVLProvider("k", "s")
        with patch.object(p, "_get_access_token", return_value="tok"):
            with patch.object(
                p, "_submit", side_effect=RuntimeError("network down")
            ):
                result = p.extract(b"fake")
        self.assertEqual(result, "")

    def test_extract_returns_empty_on_poll_timeout(self) -> None:
        p = PaddleVLProvider("k", "s", timeout=0.1, poll_interval=0.05)
        with patch.object(p, "_get_access_token", return_value="tok"):
            with patch.object(p, "_submit", return_value="task-abc"):
                with patch.object(p, "_poll", return_value=("processing", None)):
                    result = p.extract(b"fake")
        self.assertEqual(result, "")

    def test_error_on_empty_false_returns_empty_for_empty_result(self) -> None:
        p = PaddleVLProvider("k", "s", error_on_empty=False)
        with patch.object(p, "_get_access_token", return_value="tok"):
            with patch.object(p, "_submit", return_value="task-abc"):
                with patch.object(p, "_poll", return_value=("success", None)):
                    with patch.object(p, "_download_markdown", return_value=""):
                        result = p.extract(b"fake")
        self.assertEqual(result, "")

    def test_get_access_token_request(self) -> None:
        """Verify token request is well-formed."""
        p = PaddleVLProvider("key1", "secret1")
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "access_token": "tok-123",
                "expires_in": 2592000,
            }
        ).encode()
        mock_response.__enter__.return_value = mock_response
        with patch(
            "urllib.request.urlopen", return_value=mock_response
        ) as mock_urlopen:
            token = p._get_access_token()
        self.assertEqual(token, "tok-123")
        call_args = mock_urlopen.call_args[0][0]
        body = call_args.data
        self.assertIn(b"client_id=key1", body)
        self.assertIn(b"client_secret=secret1", body)


if __name__ == "__main__":
    unittest.main()
