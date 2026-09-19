"""XLSX parsing plans and feature gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto

from ooxml_llm_core.planning import ParsePurpose


class XlsxFeature(Flag):
    """Optional workbook capabilities, grouped by their source parts."""

    RICH_TEXT = auto()
    STYLE_INDEX = auto()
    SEMANTIC_STYLES = auto()
    FORMULAS = auto()
    HYPERLINKS = auto()
    COMMENTS = auto()
    SHEET_RULES = auto()
    DEFINED_NAMES = auto()
    EXTERNAL_LINKS = auto()
    RICH_VALUES = auto()
    CELL_CONTROLS = auto()
    TABLES = auto()
    DRAWINGS = auto()
    PIVOTS = auto()


_PLAIN = (
    XlsxFeature.COMMENTS
    | XlsxFeature.RICH_VALUES
    | XlsxFeature.CELL_CONTROLS
    | XlsxFeature.SHEET_RULES
    | XlsxFeature.TABLES
    | XlsxFeature.DRAWINGS
    | XlsxFeature.PIVOTS
)
_STRUCTURAL_BASE = (
    XlsxFeature.HYPERLINKS
    | XlsxFeature.COMMENTS
    | XlsxFeature.SHEET_RULES
    | XlsxFeature.DEFINED_NAMES
    | XlsxFeature.EXTERNAL_LINKS
    | XlsxFeature.RICH_VALUES
    | XlsxFeature.CELL_CONTROLS
    | XlsxFeature.TABLES
    | XlsxFeature.DRAWINGS
    | XlsxFeature.PIVOTS
)
_STRUCTURAL = _STRUCTURAL_BASE | XlsxFeature.FORMULAS | XlsxFeature.STYLE_INDEX
_SEMANTIC = _STRUCTURAL | XlsxFeature.RICH_TEXT | XlsxFeature.SEMANTIC_STYLES


@dataclass(frozen=True, slots=True)
class XlsxParsePlan:
    """Feature selection for one workbook parse."""

    purpose: ParsePurpose
    density: str
    features: XlsxFeature
    sheet_names: frozenset[str] | None = None
    cell_window: tuple[int, int, int, int] | None = None

    @property
    def module_keys(self) -> tuple[str, ...]:
        """Independent parser modules selected for this operation."""
        if self.purpose is ParsePurpose.RESOURCE:
            return ("workbook.index", "workbook.resources")
        if self.purpose is ParsePurpose.SESSION:
            return (
                "workbook.index",
                "workbook.names",
                "workbook.external_links",
                "workbook.pivots",
                "workbook.rich_values",
                "styles.semantic",
                "worksheets.semantic_cells",
            )
        cell_module = f"worksheets.{self.density}_cells"
        style_module = f"styles.{self.style_detail}"
        return ("workbook.index", style_module, cell_module, "worksheets.rules", "worksheets.resources")

    @property
    def style_detail(self) -> str:
        """Style layer required by this density's cell projection."""
        if self.density == "semantic":
            return "semantic"
        if self.density == "structural":
            return "structural"
        return "display"

    def needs(self, feature: XlsxFeature) -> bool:
        return bool(self.features & feature)

    @classmethod
    def render(cls, density: str) -> XlsxParsePlan:
        if density == "plain":
            features = _PLAIN
        elif density == "structural":
            features = _STRUCTURAL
        elif density == "semantic":
            features = _SEMANTIC
        else:
            raise ValueError("density must be one of: 'plain', 'structural', 'semantic'")
        return cls(ParsePurpose.RENDER, density, features)

    @classmethod
    def session(cls) -> XlsxParsePlan:
        return cls(ParsePurpose.SESSION, "semantic", _SEMANTIC)

    @classmethod
    def range(
        cls,
        density: str,
        sheet_name: str,
        cell_window: tuple[int, int, int, int],
    ) -> XlsxParsePlan:
        base = cls.render(density)
        return cls(base.purpose, base.density, base.features, frozenset((sheet_name,)), cell_window)

    @classmethod
    def sheet(cls, density: str, sheet_name: str) -> XlsxParsePlan:
        base = cls.render(density)
        return cls(base.purpose, base.density, base.features, frozenset((sheet_name,)))

    @classmethod
    def resource(cls, resource_type: str) -> XlsxParsePlan:
        if resource_type in {"image", "chart", "pivot_table", "embedded_object"}:
            return cls(ParsePurpose.RESOURCE, "structural", XlsxFeature.DRAWINGS | XlsxFeature.PIVOTS | XlsxFeature.TABLES)
        return cls.session()


__all__ = ["XlsxFeature", "XlsxParsePlan"]
