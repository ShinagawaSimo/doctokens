"""PPTX parsing plans and feature gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto

from ooxml_llm_core.planning import ParsePurpose

from .core.enums import Density, ResourceType


class PptxFeature(Flag):
    """Optional presentation extraction capabilities."""

    TEXT_FORMATTING = auto()
    ASSET_INDEX = auto()
    THEME_AND_LAYOUT = auto()
    GEOMETRY = auto()
    NOTES = auto()
    COMMENTS = auto()
    OBJECT_DETAILS = auto()
    OCR = auto()
    NAVIGATION = auto()


_BASE = PptxFeature.NOTES | PptxFeature.COMMENTS | PptxFeature.OBJECT_DETAILS | PptxFeature.ASSET_INDEX | PptxFeature.NAVIGATION
_FULL = _BASE | PptxFeature.TEXT_FORMATTING | PptxFeature.THEME_AND_LAYOUT | PptxFeature.OCR


@dataclass(frozen=True, slots=True)
class PptxParsePlan:
    """Feature selection for one presentation operation."""

    purpose: ParsePurpose
    density: Density
    features: PptxFeature

    @property
    def module_keys(self) -> tuple[str, ...]:
        """Independent parser modules selected for this operation."""
        if self.purpose is ParsePurpose.RESOURCE:
            return ("resources.assets", "resources.objects")
        if self.purpose is ParsePurpose.SESSION or self.density is Density.SEMANTIC:
            return (
                "presentation.index",
                "slides.semantic",
                "ancillary.notes",
                "ancillary.comments",
                "resources.assets",
                "resources.objects.full",
                "ocr",
            )
        return (
            "presentation.index",
            f"slides.{self.density.value}",
            "ancillary.notes",
            "ancillary.comments",
            "resources.assets",
            "resources.objects.summary",
        )

    def needs(self, feature: PptxFeature) -> bool:
        return bool(self.features & feature)

    @classmethod
    def render(cls, density: Density | str) -> PptxParsePlan:
        resolved = Density.parse(density)
        if resolved is Density.SEMANTIC:
            return cls(ParsePurpose.RENDER, resolved, _FULL)
        return cls(ParsePurpose.RENDER, resolved, _BASE)

    @classmethod
    def session(cls) -> PptxParsePlan:
        return cls(ParsePurpose.SESSION, Density.SEMANTIC, _FULL)

    @classmethod
    def resource(cls, resource_type: ResourceType | str) -> PptxParsePlan:
        resolved = ResourceType.parse(resource_type)
        if resolved in {ResourceType.IMAGE, ResourceType.MEDIA}:
            return cls(ParsePurpose.RESOURCE, Density.STRUCTURAL, PptxFeature(0))
        return cls(ParsePurpose.RESOURCE, Density.STRUCTURAL, PptxFeature.OBJECT_DETAILS)


__all__ = ["PptxFeature", "PptxParsePlan"]
