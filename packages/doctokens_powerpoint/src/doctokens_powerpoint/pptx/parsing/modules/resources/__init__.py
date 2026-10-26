"""PPTX asset and embedded-object modules."""

from .assets import AssetExtractor
from .objects import EmbeddedObjectExtractor

__all__ = ["AssetExtractor", "EmbeddedObjectExtractor"]
