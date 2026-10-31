"""Keep Tesseract's complete TXT while reading actual word confidences from TSV."""

from __future__ import annotations

import csv
import time
from io import StringIO
from typing import Any

from ..models import weighted_confidence


def recognize(engine: Any, image: Any, kwargs: dict[str, object]) -> tuple[str, float | None]:
    timeout = kwargs.get("timeout")
    deadline = time.monotonic() + float(timeout) if isinstance(timeout, (int, float)) else None
    multiple = getattr(engine, "run_and_get_multiple_output", None)
    if callable(multiple):
        output = multiple(image, extensions=["txt", "tsv"], **kwargs)
        if isinstance(output, (list, tuple)) and len(output) == 2 and all(isinstance(item, str) for item in output):
            return output[0], _confidence(output[1])
    text_kwargs = dict(kwargs)
    if deadline is not None:
        text_remaining = deadline - time.monotonic()
        if text_remaining <= 0:
            raise TimeoutError("OCR request deadline exceeded")
        text_kwargs["timeout"] = text_remaining
    text = engine.image_to_string(image, **text_kwargs)
    remaining = deadline - time.monotonic() if deadline is not None else None
    if remaining is not None and remaining <= 0:
        return text, None
    data_method = getattr(engine, "image_to_data", None)
    if not callable(data_method):
        return text, None
    score_kwargs = dict(kwargs)
    if remaining is not None:
        score_kwargs["timeout"] = remaining
    try:
        data = data_method(image, **score_kwargs)
        return text, _confidence(data) if isinstance(data, str) else None
    except Exception:
        # Available text remains readable even when the optional score pass fails.
        return text, None


def _confidence(tsv: str) -> float | None:
    samples: list[tuple[str, float | None]] = []
    for row in csv.DictReader(StringIO(tsv), delimiter="\t"):
        text, score = row.get("text"), row.get("conf")
        if not isinstance(text, str):
            continue
        try:
            value = float(score) / 100 if isinstance(score, str) else None
        except ValueError:
            value = None
        samples.append((text, value))
    return weighted_confidence(samples)
