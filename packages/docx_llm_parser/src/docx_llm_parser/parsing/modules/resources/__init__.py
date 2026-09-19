"""DOCX resource indexing and object parsing modules."""

from .assets import IMAGE_REL_TYPE, AssetExtractor
from .objects import EmbeddedObjectExtractor

__all__ = ["IMAGE_REL_TYPE", "AssetExtractor", "EmbeddedObjectExtractor"]
