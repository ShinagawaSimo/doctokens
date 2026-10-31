"""OCR provider contract and normalized result values."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterable
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
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
            or self.status is not OcrStatus.SUCCESS
        ):
            raise ValueError("confidence requires successful OCR and a finite score between zero and one")
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
    def from_text(cls, text: object, *, confidence: float | None = None) -> OcrResult:
        if not isinstance(text, str):
            return cls.error("invalid_result", "OCR provider returned a non-string value")
        cleaned = text.strip()
        return cls(OcrStatus.SUCCESS, cleaned, confidence=confidence) if cleaned else cls(OcrStatus.EMPTY)

    @classmethod
    def error(cls, code: object, message: object = None) -> OcrResult:
        normalized_code = code.strip()[:100] if isinstance(code, str) else ""
        if not normalized_code:
            normalized_code = "provider_error"
        normalized_message = message.strip()[:300] if isinstance(message, str) and message.strip() else None
        return cls(OcrStatus.ERROR, error_code=normalized_code, error_message=normalized_message)

    def to_record(self) -> dict[str, str | bool]:
        """Return a parser-neutral record suitable for document models."""
        record: dict[str, str | bool] = {"status": self.status.value, "text": self.text}
        if self.confidence is not None and self.confidence < 0.8:
            record["low_confidence"] = True
        if self.error_code:
            record["error_code"] = self.error_code
        if self.error_message:
            record["error_message"] = self.error_message
        return record


def weighted_confidence(samples: Iterable[tuple[str, float | None]]) -> float | None:
    """Aggregate available recognition scores by non-whitespace character count."""
    values: list[float] = []
    count = 0
    for text, score in samples:
        if (
            score is None
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 0 <= score <= 1
        ):
            continue
        weight = sum(not character.isspace() for character in text)
        if weight:
            count += weight
            values.append(score * weight)
    return math.fsum(values) / count if count else None


class OcrProvider(ABC):
    """OCR interface returning a structured recognition result."""

    # Providers are conservative by default. Adapters may raise this when
    # their implementation is safe to call concurrently.
    max_concurrency = 1
    # A timeout can only be guaranteed when the engine exposes cancellation.
    # Thread-based wrappers cannot safely terminate a running native inference.
    supports_timeout = False

    @abstractmethod
    def extract_result(self, image_bytes: bytes, *, timeout: float | None = None) -> OcrResult:
        """Recognize bytes, preserving success, empty and error outcomes."""
        ...


__all__ = ["OcrProvider", "OcrResult", "OcrStatus"]
