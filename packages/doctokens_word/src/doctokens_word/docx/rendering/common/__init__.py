"""Density-independent renderer helpers shared by all output surfaces."""

from .controls import wrap_plain_control
from .text import filter_format, merge_text_runs, run_output_signature

__all__ = [
    "filter_format",
    "merge_text_runs",
    "run_output_signature",
    "wrap_plain_control",
]
