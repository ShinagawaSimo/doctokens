"""Document-level density orchestration and block dispatch."""

from .blocks import render_block
from .pipeline import iter_plain, iter_semantic, iter_structural, supplemental_to_output

__all__ = [
    "iter_plain",
    "iter_semantic",
    "iter_structural",
    "render_block",
    "supplemental_to_output",
]
