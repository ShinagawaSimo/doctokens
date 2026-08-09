"""Contract tests for PaddleVLProvider — no network calls."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from ocr_llm_core._paddle_vl import PaddleVLProvider, _json_object, _object_map


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
        self.assertEqual(p.poll_interval, 1.0)
        self.assertEqual(p.timeout, 120)
        self.assertTrue(p.error_on_empty)

    def test_extract_returns_markdown_on_success(self) -> None:
        """Simulate full submit→poll→download flow."""
        p = PaddleVLProvider("k", "s")
        expected = "## Title\n\nParagraph text\n\n| A | B |\n|---|---|\n| 1 | 2 |"

        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", return_value="task-abc"),
            patch.object(p, "_poll", return_value=("success", None)),
            patch.object(p, "_download_markdown", return_value=expected),
        ):
            result = p.extract(b"fake-image-bytes")
        self.assertEqual(result, expected)

    def test_extract_returns_empty_on_api_failure(self) -> None:
        p = PaddleVLProvider("k", "s")
        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", side_effect=RuntimeError("network down")),
        ):
            result = p.extract(b"fake")
        self.assertEqual(result, "")

    def test_extract_returns_empty_on_poll_timeout(self) -> None:
        p = PaddleVLProvider("k", "s", timeout=0.1, poll_interval=0.05)
        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", return_value="task-abc"),
            patch.object(p, "_poll", return_value=("processing", None)),
        ):
            result = p.extract(b"fake")
        self.assertEqual(result, "")

    def test_error_on_empty_false_returns_empty_for_empty_result(self) -> None:
        p = PaddleVLProvider("k", "s", error_on_empty=False)
        with (
            patch.object(p, "_get_access_token", return_value="tok"),
            patch.object(p, "_submit", return_value="task-abc"),
            patch.object(p, "_poll", return_value=("success", None)),
            patch.object(p, "_download_markdown", return_value=""),
        ):
            result = p.extract(b"fake")
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
            _json_object(b"[]")
        self.assertEqual(_object_map("not-a-map"), {})

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
            task_id = p._submit("tok", b"abc")

        self.assertEqual(task_id, "task-1")
        request = mock_urlopen.call_args[0][0]
        payload = json.loads(request.data)
        self.assertEqual(payload["fileType"], 1)
        self.assertEqual(payload["language"], "cht")

        with (
            patch(
                "urllib.request.urlopen",
                return_value=_response({"error_code": 17, "error_msg": "bad request"}),
            ),
            self.assertRaises(RuntimeError),
        ):
            p._submit("tok", b"abc")

    def test_poll_success_and_api_error(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        with patch(
            "urllib.request.urlopen",
            return_value=_response({"error_code": 0, "result": {"status": "success"}}),
        ):
            self.assertEqual(p._poll("tok", "task-1"), ("success", None))

        with patch(
            "urllib.request.urlopen",
            return_value=_response({"error_code": 2, "error_msg": "quota"}),
        ):
            self.assertEqual(p._poll("tok", "task-1"), ("failed", "quota"))

    def test_download_markdown_success_and_empty(self) -> None:
        p = PaddleVLProvider("key1", "secret1")
        with patch(
            "urllib.request.urlopen",
            return_value=_response({"result": {"markdown_url": ""}}),
        ):
            self.assertEqual(p._download_markdown("tok", "task-1"), "")

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _response({"result": {"markdown_url": "https://example.test/doc.md"}}),
                _response(b"# Parsed"),
            ],
        ):
            self.assertEqual(p._download_markdown("tok", "task-1"), "# Parsed")


if __name__ == "__main__":
    unittest.main()
