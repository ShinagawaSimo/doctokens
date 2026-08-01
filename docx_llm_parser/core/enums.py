"""Validated string enums used at public API boundaries."""

from __future__ import annotations

from enum import Enum


class StringEnum(str, Enum):
    """Python 3.10-compatible string enum with stable display behavior."""

    def __str__(self) -> str:
        return str(self.value)


class Density(StringEnum):
    """Amount of document detail retained by a renderer."""

    PLAIN = "L0"
    STRUCTURAL = "L1"
    SEMANTIC = "L2"

    @classmethod
    def parse(cls, value: Density | str) -> Density:
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError("density must be one of: 'L0', 'L1', 'L2'") from exc


class RevisionMode(StringEnum):
    """Visibility policy for tracked document revisions."""

    FINAL = "final"
    ORIGINAL = "original"
    REVIEW = "review"

    @classmethod
    def parse(cls, value: RevisionMode | str) -> RevisionMode:
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError("revision_mode must be one of: 'final', 'original', 'review'") from exc


class ResourceType(StringEnum):
    """Supported resource collection and detail query names."""

    IMAGES = "images"
    IMAGE = "image"
    CHARTS = "charts"
    CHART = "chart"
    SMARTARTS = "smartarts"
    SMARTART = "smartart"
    TABLES = "tables"
    TABLE = "table"

    @property
    def is_plural(self) -> bool:
        return self in {
            ResourceType.IMAGES,
            ResourceType.CHARTS,
            ResourceType.SMARTARTS,
            ResourceType.TABLES,
        }

    @classmethod
    def parse(cls, value: ResourceType | str) -> ResourceType:
        try:
            return cls(value)
        except ValueError as exc:
            supported = ", ".join(item.value for item in cls)
            raise ValueError(
                f"Unknown resource type {value!r}; expected one of: {supported}"
            ) from exc
