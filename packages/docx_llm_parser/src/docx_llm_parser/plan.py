"""DOCX parsing plans.

Plans describe the exact information required by one operation. They keep
selection policy out of extractors and make skipped work explicit in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto

from ooxml_llm_core.planning import ParsePurpose

from .core.enums import Density, ResourceType


class DocxFeature(Flag):
    """Expensive DOCX extraction capabilities."""

    BODY = auto()
    ASSET_INDEX = auto()
    CHARACTER_FORMATTING = auto()
    RAW_HINTS = auto()
    HEADERS = auto()
    FOOTERS = auto()
    FOOTNOTES = auto()
    ENDNOTES = auto()
    COMMENTS = auto()
    COMMENT_THREADING = auto()
    EMBEDDED_DETAILS = auto()
    OCR = auto()


_RENDER_BASE = (
    DocxFeature.BODY
    | DocxFeature.ASSET_INDEX
    | DocxFeature.FOOTNOTES
    | DocxFeature.ENDNOTES
    | DocxFeature.COMMENTS
)
_FULL = (
    DocxFeature.CHARACTER_FORMATTING
    | DocxFeature.RAW_HINTS
    | DocxFeature.BODY
    | DocxFeature.ASSET_INDEX
    | DocxFeature.HEADERS
    | DocxFeature.FOOTERS
    | DocxFeature.FOOTNOTES
    | DocxFeature.ENDNOTES
    | DocxFeature.COMMENTS
    | DocxFeature.COMMENT_THREADING
    | DocxFeature.EMBEDDED_DETAILS
    | DocxFeature.OCR
)


@dataclass(frozen=True, slots=True)
class DocxParsePlan:
    """Feature selection for one DOCX operation."""

    purpose: ParsePurpose
    density: Density
    features: DocxFeature

    def needs(self, feature: DocxFeature) -> bool:
        return bool(self.features & feature)

    @classmethod
    def render(cls, density: Density | str) -> DocxParsePlan:
        resolved = Density.parse(density)
        if resolved is Density.SEMANTIC:
            return cls(ParsePurpose.RENDER, resolved, _FULL)
        return cls(ParsePurpose.RENDER, resolved, _RENDER_BASE | DocxFeature.EMBEDDED_DETAILS)

    @classmethod
    def session(cls) -> DocxParsePlan:
        return cls(ParsePurpose.SESSION, Density.SEMANTIC, _FULL)

    @classmethod
    def resource(cls, resource_type: ResourceType | str) -> DocxParsePlan:
        resolved = ResourceType.parse(resource_type)
        if resolved is ResourceType.IMAGE:
            return cls(ParsePurpose.RESOURCE, Density.STRUCTURAL, DocxFeature.ASSET_INDEX)
        if resolved in {ResourceType.CHART, ResourceType.SMARTART}:
            return cls(ParsePurpose.RESOURCE, Density.STRUCTURAL, DocxFeature.EMBEDDED_DETAILS)
        return cls(
            ParsePurpose.RESOURCE,
            Density.STRUCTURAL,
            DocxFeature.BODY | DocxFeature.ASSET_INDEX | DocxFeature.EMBEDDED_DETAILS,
        )


__all__ = ["DocxFeature", "DocxParsePlan"]
