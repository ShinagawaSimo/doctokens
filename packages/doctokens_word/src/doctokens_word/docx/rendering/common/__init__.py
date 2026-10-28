"""Density-independent renderer helpers shared by all output surfaces."""

from .controls import wrap_plain_control
from .ocr import ocr_text
from .text import filter_format, merge_text_runs, run_output_signature

__all__ = [
    "filter_format",
    "merge_text_runs",
    "ocr_text",
    "run_output_signature",
    "wrap_plain_control",
]
