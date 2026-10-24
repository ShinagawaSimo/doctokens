"""Final output renderers for LLM-facing self-defined markup."""

from .dispatch import iter_output, to_output

__all__ = [
    "iter_output",
    "to_output",
]
