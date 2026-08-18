"""PPTX debug artifacts and content metrics."""

from __future__ import annotations

from dataclasses import asdict

from ooxml_llm_core.debug import DebugWriter
from ooxml_llm_core.metrics import MetricsRecorder
from ooxml_llm_core.models import ParseWarning

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


def write_debug_artifacts(debug: DebugWriter, parsed: ParsedPresentation) -> None:
    """Write diagnostics fail-soft; debug output must never break parsing."""
    try:
        debug.write_json("slides.json", parsed.slides)
        debug.write_json(
            "manifest.json",
            {
                "slideSize": parsed.slide_size,
                "assets": parsed.assets,
                "charts": list(parsed.charts),
                "smartarts": list(parsed.smartarts),
                "theme": parsed.theme,
                "comments": parsed.comments,
                "ocrResults": parsed.ocr_results,
            },
        )
        debug.write_json("warnings.json", [asdict(item) for item in parsed.warnings])
        debug.write_json("metrics.json", parsed.metrics)
    except Exception as exc:
        parsed.warnings.append(ParseWarning(code="DEBUG_WRITE_FAILED", message=f"Failed to write debug artifacts: {exc}"))
