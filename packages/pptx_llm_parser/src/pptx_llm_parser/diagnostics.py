"""PPTX in-memory content metrics."""

from __future__ import annotations

from ooxml_llm_core.metrics import MetricsRecorder

from .core.models import ParsedPresentation


def record_metrics(parsed: ParsedPresentation, recorder: MetricsRecorder) -> None:
    recorder.set_counter("slideCount", len(parsed.slides))
    recorder.set_counter("shapeCount", sum(len(slide["shapes"]) for slide in parsed.slides))
    recorder.set_counter("assetCount", len(parsed.assets))
    recorder.set_counter("chartCount", len(parsed.charts))
    recorder.set_counter("smartartCount", len(parsed.smartarts))
    recorder.set_counter("commentCount", len(parsed.comments))
    recorder.set_counter("ocrResultCount", len(parsed.ocr_results))
    recorder.set_counter("warningCount", len(parsed.warnings))
