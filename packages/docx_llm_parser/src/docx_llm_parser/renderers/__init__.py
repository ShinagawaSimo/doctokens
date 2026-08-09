"""Final output renderers for LLM-facing markup."""

from .html5 import iter_html5, to_html5, write_outputs

__all__ = [
    "iter_html5",
    "to_html5",
    "write_outputs",
]
