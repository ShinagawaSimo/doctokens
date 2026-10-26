"""OCR provider contract and normalized result values."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class OcrStatus(str, Enum):
    """Outcome category for one OCR attempt."""

    SUCCESS = "success"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Normalized OCR outcome."""

    status: OcrStatus
    text: str = ""
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, OcrStatus):
            raise TypeError("status must be an OcrStatus")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if self.status is OcrStatus.SUCCESS:
            if not self.text:
                raise ValueError("successful OCR results must contain text")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("successful OCR results cannot contain error fields")
        elif self.status is OcrStatus.EMPTY:
            if self.text:
                raise ValueError("empty OCR results cannot contain text")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("empty OCR results cannot contain error fields")
        else:
            if not isinstance(self.error_code, str) or not self.error_code.strip():
                raise ValueError("OCR errors require a non-empty error_code")
            if self.text:
                raise ValueError("OCR errors cannot contain text")

    @classmethod
    def from_text(cls, text: object) -> OcrResult:
        if not isinstance(text, str):
            return cls.error("invalid_result", "OCR provider returned a non-string value")
        cleaned = text.strip()
        return cls(OcrStatus.SUCCESS, cleaned) if cleaned else cls(OcrStatus.EMPTY)

    @classmethod
    def error(cls, code: object, message: object = None) -> OcrResult:
        normalized_code = code.strip()[:100] if isinstance(code, str) else ""
        if not normalized_code:
            normalized_code = "provider_error"
        normalized_message = message.strip()[:300] if isinstance(message, str) and message.strip() else None
        return cls(OcrStatus.ERROR, error_code=normalized_code, error_message=normalized_message)

    def to_record(self) -> dict[str, str]:
        """Return a parser-neutral record suitable for document models."""
        record = {"status": self.status.value, "text": self.text}
        if self.error_code:
            record["error_code"] = self.error_code
        if self.error_message:
            record["error_message"] = self.error_message
        return record


class OcrProvider(ABC):
    """Minimal OCR interface with a diagnostics-preserving adapter method."""

    # Providers are conservative by default. Adapters may raise this when
    # their implementation is safe to call concurrently.
    max_concurrency = 1
    # A timeout can only be guaranteed when the engine exposes cancellation.
    # Thread-based wrappers cannot safely terminate a running native inference.
    supports_timeout = False

    @abstractmethod
    def extract(self, image_bytes: bytes) -> str:
        """Extract text from image bytes, returning an empty string for no text."""
        ...

    def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
        """Run the legacy ``extract`` method and normalize its outcome."""
        del timeout
        try:
            return OcrResult.from_text(self.extract(image_bytes))
        except TimeoutError as exc:
            return OcrResult.error("timeout", _error_message(exc))
        except Exception as exc:
            return OcrResult.error("provider_error", _error_message(exc))


def _error_message(error: BaseException) -> str:
    message = str(error).strip() or error.__class__.__name__
    return message[:300]


__all__ = ["OcrProvider", "OcrResult", "OcrStatus"]
