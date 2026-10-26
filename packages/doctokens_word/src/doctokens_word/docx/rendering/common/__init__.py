"""Density-independent renderer helpers shared by all output surfaces."""

from .controls import control_attrs, wrap_control, wrap_plain_control
from .ocr import ocr_text, render_ocr_result
from .text import filter_format, merge_text_runs, run_output_signature

__all__ = [
    "control_attrs",
    "filter_format",
    "merge_text_runs",
    "ocr_text",
    "render_ocr_result",
    "run_output_signature",
    "wrap_control",
    "wrap_plain_control",
]
