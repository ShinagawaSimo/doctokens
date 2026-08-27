"""PPTX in-memory content metrics."""

from __future__ import annotations

from ooxml_llm_core.metrics import MetricsRecorder

from .core.models import ParsedPresentation


def record_metrics(parsed_presentation: ParsedPresentation, recorder: MetricsRecorder) -> None:
    """Record presentation-level counts used by output and performance checks."""
    recorder.set_counter("slideCount", len(parsed_presentation.slides))
    recorder.set_counter(
        "shapeCount",
        sum(len(slide["shapes"]) for slide in parsed_presentation.slides),
    )
    recorder.set_counter("assetCount", len(parsed_presentation.assets))
    recorder.set_counter("chartCount", len(parsed_presentation.charts))
    recorder.set_counter("smartartCount", len(parsed_presentation.smartarts))
    recorder.set_counter("commentCount", len(parsed_presentation.comments))
    recorder.set_counter("ocrResultCount", len(parsed_presentation.ocr_results))
    recorder.set_counter("warningCount", len(parsed_presentation.warnings))
