"""PPTX to LLM-readable semantic HTML5 parser."""

from ._version import __version__
from .api import parse_pptx
from .core.enums import Density, ResourceType

__all__ = [
    "Density",
    "ResourceType",
    "__version__",
    "parse_pptx",
]
