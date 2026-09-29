"""PaddleOCR-VL cloud API adapter (built-in, zero extra dependencies)."""

from __future__ import annotations

import base64
import json
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

from ._image_headers import _image_dimensions, _image_suffix
from ._provider import OcrProvider, OcrResult

_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_SUBMIT_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task"
_QUERY_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task/query"
_MAX_JSON_BYTES = 1 * 1024 * 1024
_MAX_MARKDOWN_BYTES = 20 * 1024 * 1024
_ALLOWED_RESULT_SUFFIXES = ("bcebos.com", "baidubce.com")
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_IMAGE_EDGE = 8192


def _parse_json_object(raw: bytes) -> dict[str, object]:
    parsed: object = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("Unexpected JSON response shape")
    return cast(dict[str, object], parsed)


def _object_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)


class _RateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be greater than zero")
        self._interval = 1.0 / requests_per_second
        self._next = 0.0
        self._lock = threading.Lock()

    def acquire(self, deadline: float | None) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            if deadline is not None and now + delay >= deadline:
                raise TimeoutError("OCR request rate-limit wait exceeded timeout")
            if delay:
                time.sleep(delay)
            self._next = time.monotonic() + self._interval


class _ValidatedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        _validate_result_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


class PaddleVLProvider(OcrProvider):
    """OCR via Baidu PaddleOCR-VL document parsing API."""

    # The public API allows two submit requests per second.  Keeping this
    # bound on the provider also protects callers that use the shared batcher.
    max_concurrency = 2
    supports_timeout = True

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        language: str = "cht",
        poll_interval: float = 5.0,
        timeout: float = 120.0,
        error_on_empty: bool = False,
        max_input_bytes: int = _MAX_IMAGE_BYTES,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip() or not isinstance(secret_key, str) or not secret_key.strip():
            raise ValueError("api_key and secret_key must not be empty")
        if (
            isinstance(poll_interval, bool)
            or not isinstance(poll_interval, (int, float))
            or not math.isfinite(poll_interval)
            or poll_interval <= 0
        ):
            raise ValueError("poll_interval must be greater than zero")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if not isinstance(error_on_empty, bool):
            raise TypeError("error_on_empty must be a boolean")
        if isinstance(max_input_bytes, bool) or not isinstance(max_input_bytes, int) or max_input_bytes <= 0:
            raise ValueError("max_input_bytes must be greater than zero")
        if max_input_bytes > _MAX_IMAGE_BYTES:
            raise ValueError("max_input_bytes cannot exceed the PaddleOCR-VL 10 MiB image limit")
        self.api_key = api_key
        self.secret_key = secret_key
        # Kept for source compatibility. The current PaddleOCR-VL endpoint
        # determines language automatically and does not accept this field.
        self.language = language
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.error_on_empty = error_on_empty
        self.max_input_bytes = max_input_bytes
        self._token: str | None = None
        self._token_deadline = 0.0
        self._token_lock = threading.Lock()
        self._submit_limiter = _RateLimiter(2.0)
        self._query_limiter = _RateLimiter(5.0)

    def extract(self, image_bytes: bytes) -> str:
        return self.extract_result(image_bytes).text

    def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
        if not isinstance(image_bytes, bytes) or not image_bytes:
            return OcrResult.error("invalid_image", "image_bytes must be non-empty bytes")
        if len(image_bytes) > self.max_input_bytes:
            return OcrResult.error("input_too_large", "image exceeds max_input_bytes")
        file_suffix = _image_suffix(image_bytes)
        if file_suffix is None:
            return OcrResult.error("unsupported_image", "PaddleOCR-VL requires PNG, JPEG, BMP, or TIFF image bytes")
        dimensions = _image_dimensions(image_bytes, file_suffix)
        if dimensions is not None:
            width, height = dimensions
            if width <= 0 or height <= 0:
                return OcrResult.error("invalid_image", "image has invalid dimensions")
            if max(width, height) > _MAX_IMAGE_EDGE:
                return OcrResult.error("image_too_large", "image exceeds the PaddleOCR-VL 8192-pixel edge limit")
        budget = self.timeout if timeout is None else timeout
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget <= 0:
            return OcrResult.error("timeout", "OCR timeout must be greater than zero")
        deadline = time.monotonic() + budget
        try:
            token = self._get_access_token(deadline)
            task_id = self._submit(token, image_bytes, deadline, file_suffix=file_suffix)
            status, error_message, result = self._poll(token, task_id, deadline)
            if status != "success":
                code = "timeout" if status == "timeout" else "api_error"
                return OcrResult.error(code, error_message or "PaddleOCR task failed")
            markdown_url = result.get("markdown_url")
            text = self._download_markdown(token, task_id, deadline, markdown_url)
            if not text and self.error_on_empty:
                return OcrResult.error("empty_result", "PaddleOCR returned no text")
            return OcrResult.from_text(text)
        except TimeoutError as exc:
            return OcrResult.error("timeout", str(exc) or "OCR timed out")
        except urllib.error.URLError as exc:
            return OcrResult.error("network_error", _error_message(exc))
        except Exception as exc:
            return OcrResult.error("adapter_error", _error_message(exc))

    def _get_access_token(self, deadline: float | None = None) -> str:
        now = time.monotonic()
        if self._token is not None and now + 60 < self._token_deadline:
            return self._token
        with self._token_lock:
            now = time.monotonic()
            if self._token is not None and now + 60 < self._token_deadline:
                return self._token
            data = urllib.parse.urlencode(
                {
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.secret_key,
                }
            ).encode()
            req = urllib.request.Request(_TOKEN_URL, data=data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=_request_timeout(deadline, 30.0)) as resp:
                body = _parse_json_object(_read_limited(resp, _MAX_JSON_BYTES))
            token = body.get("access_token")
            if not isinstance(token, str) or not token:
                raise RuntimeError("Token response did not include access_token")
            expires_in = body.get("expires_in", 3600)
            try:
                candidate = float(expires_in) if isinstance(expires_in, (int, float, str)) else 3600.0
                lifetime = max(0.0, candidate) if math.isfinite(candidate) else 3600.0
            except (TypeError, ValueError):
                lifetime = 3600.0
            self._token = token
            self._token_deadline = time.monotonic() + lifetime
            return token

    def _submit(
        self,
        token: str,
        image_bytes: bytes,
        deadline: float | None = None,
        *,
        file_suffix: str | None = None,
    ) -> str:
        self._submit_limiter.acquire(deadline)
        suffix = file_suffix or _image_suffix(image_bytes)
        if suffix is None:
            raise ValueError("Unsupported image format")
        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = urllib.parse.urlencode({"file_data": b64, "file_name": f"image.{suffix}"}).encode()
        req = urllib.request.Request(_with_token(_SUBMIT_URL, token), data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=_request_timeout(deadline, 60.0)) as resp:
            body = _parse_json_object(_read_limited(resp, _MAX_JSON_BYTES))
        if body.get("error_code", 0) != 0:
            raise RuntimeError(f"Submit failed: {body.get('error_msg', 'unknown')}")
        task_id = _object_mapping(body.get("result")).get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError("Submit response did not include task_id")
        return task_id

    def _poll(
        self,
        token: str,
        task_id: str,
        deadline: float | None = None,
    ) -> tuple[str, str | None, dict[str, object]]:
        own_deadline = time.monotonic() + self.timeout if deadline is None else deadline
        while time.monotonic() < own_deadline:
            body = self._query(token, task_id, own_deadline)
            if body.get("error_code", 0) != 0:
                error_msg = body.get("error_msg")
                return ("failed", error_msg if isinstance(error_msg, str) else "unknown", {})
            result = _object_mapping(body.get("result"))
            status_value = result.get("status")
            if not isinstance(status_value, str):
                return ("failed", "PaddleOCR query response did not include a valid status", result)
            status = status_value.lower()
            if status in ("success", "failed"):
                task_error = result.get("task_error")
                return (status, task_error if isinstance(task_error, str) else None, result)
            if status not in ("pending", "processing"):
                return ("failed", f"PaddleOCR returned unknown task status: {status}", result)
            remaining = own_deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(self.poll_interval, remaining))
        return ("timeout", "PaddleOCR task timed out", {})

    def _query(self, token: str, task_id: str, deadline: float | None) -> dict[str, object]:
        self._query_limiter.acquire(deadline)
        payload = urllib.parse.urlencode({"task_id": task_id}).encode()
        req = urllib.request.Request(_with_token(_QUERY_URL, token), data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=_request_timeout(deadline, 30.0)) as resp:
            return _parse_json_object(_read_limited(resp, _MAX_JSON_BYTES))

    def _download_markdown(
        self,
        token: str,
        task_id: str,
        deadline: float | None = None,
        markdown_url: object = None,
    ) -> str:
        if not isinstance(markdown_url, str) or not markdown_url:
            result = _object_mapping(self._query(token, task_id, deadline).get("result"))
            markdown_url = result.get("markdown_url")
        if not isinstance(markdown_url, str) or not markdown_url:
            return ""
        _validate_result_url(markdown_url)
        opener = urllib.request.build_opener(_ValidatedRedirectHandler())
        with opener.open(markdown_url, timeout=_request_timeout(deadline, 30.0)) as resp:
            final_url = resp.geturl() if hasattr(resp, "geturl") else markdown_url
            if isinstance(final_url, str):
                _validate_result_url(final_url)
            data = _read_limited(resp, _MAX_MARKDOWN_BYTES)
        return data.decode("utf-8")


def _with_token(url: str, token: str) -> str:
    return f"{url}?{urllib.parse.urlencode({'access_token': token})}"


def _request_timeout(deadline: float | None, maximum: float) -> float:
    if deadline is None:
        return maximum
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("OCR request deadline exceeded")
    return min(maximum, remaining)


def _read_limited(response: Any, limit: int) -> bytes:
    data = response.read(limit + 1)
    if not isinstance(data, bytes):
        raise RuntimeError("Unexpected non-byte response body")
    content_length = getattr(response, "headers", {}).get("Content-Length")
    if isinstance(content_length, str):
        try:
            if int(content_length) > limit:
                raise RuntimeError("OCR response exceeds configured size limit")
        except ValueError:
            pass
    if len(data) > limit:
        raise RuntimeError("OCR response exceeds configured size limit")
    return data


def _validate_result_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or not any(host == suffix or host.endswith("." + suffix) for suffix in _ALLOWED_RESULT_SUFFIXES)
    ):
        raise RuntimeError("PaddleOCR returned a disallowed markdown URL")


def _error_message(error: BaseException) -> str:
    message = str(error).strip() or error.__class__.__name__
    message = re.sub(r"(?i)(access_token|client_secret)=([^&\s]+)", r"\1=<redacted>", message)
    return message[:300]


__all__ = ["PaddleVLProvider"]
