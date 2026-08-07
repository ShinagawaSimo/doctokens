"""PaddleOCR-VL cloud API adapter (built-in, zero extra dependencies)."""

from __future__ import annotations

import base64
import json
import time
import urllib.request

from ._provider import OcrProvider

_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_SUBMIT_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task"
_QUERY_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task/query"


class PaddleVLProvider(OcrProvider):
    """OCR via Baidu PaddleOCR-VL document parsing API.

    Encodes *image_bytes* as base64, submits an async parsing task,
    polls for completion, and returns the resulting markdown.
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        language: str = "cht",
        poll_interval: float = 1.0,
        timeout: float = 120.0,
        error_on_empty: bool = True,
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.language = language
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.error_on_empty = error_on_empty

    # -- public API --

    def extract(self, image_bytes: bytes) -> str:
        try:
            token = self._get_access_token()
            task_id = self._submit(token, image_bytes)
            status, _error_msg = self._poll(token, task_id)
            if status != "success":
                return ""
            text = self._download_markdown(token, task_id)
            if not text and self.error_on_empty:
                return ""
            return text
        except Exception:
            return ""

    # -- internal helpers --

    def _get_access_token(self) -> str:
        data = (
            f"grant_type=client_credentials"
            f"&client_id={self.api_key}"
            f"&client_secret={self.secret_key}"
        ).encode()
        req = urllib.request.Request(_TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
        return body["access_token"]

    def _submit(self, token: str, image_bytes: bytes) -> str:
        b64 = base64.b64encode(image_bytes).decode()
        payload = json.dumps(
            {
                "file": b64,
                "fileType": 1,
                "language": self.language,
            }
        ).encode()
        url = f"{_SUBMIT_URL}?access_token={token}"
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
        if body.get("error_code", 0) != 0:
            raise RuntimeError(f"Submit failed: {body.get('error_msg', 'unknown')}")
        return body["result"]["task_id"]

    def _poll(self, token: str, task_id: str) -> tuple[str, str | None]:
        payload = json.dumps({"task_id": task_id}).encode()
        url = f"{_QUERY_URL}?access_token={token}"
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
            if body.get("error_code", 0) != 0:
                return ("failed", body.get("error_msg", "unknown"))
            result = body.get("result", {})
            status = result.get("status", "failed")
            if status in ("success", "failed"):
                return (status, result.get("task_error"))
            time.sleep(self.poll_interval)
        return ("processing", None)

    def _download_markdown(self, token: str, task_id: str) -> str:
        payload = json.dumps({"task_id": task_id}).encode()
        url = f"{_QUERY_URL}?access_token={token}"
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
        markdown_url = body["result"].get("markdown_url")
        if not markdown_url:
            return ""
        with urllib.request.urlopen(markdown_url, timeout=30) as resp:
            return resp.read().decode("utf-8")
