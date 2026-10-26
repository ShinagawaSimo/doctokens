"""XLSX parsing plans and feature gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto

from doctokens_core.runtime.planning import ParsePurpose


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
    columns: frozenset[int] | None = None
    annotation_cells: bool | None = None
    display_text: bool = True
    scan_cells: bool = True
    retain_cells: bool = True
    formula_only: bool = False
    preview: bool = False

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
        return cls(ParsePurpose.RENDER, density, features, preview=True)

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
        return cls(base.purpose, base.density, base.features, frozenset((sheet_name,)), preview=True)

    @classmethod
    def resource(cls, resource_type: str) -> XlsxParsePlan:
        if resource_type in {"image", "chart", "pivot_table", "embedded_object"}:
            return cls(ParsePurpose.RESOURCE, "structural", XlsxFeature.DRAWINGS | XlsxFeature.PIVOTS | XlsxFeature.TABLES)
        return cls.session()

    @classmethod
    def values(
        cls,
        sheet_name: str,
        *,
        window: tuple[int, int, int, int] | None = None,
        columns: frozenset[int] | None = None,
        annotations: bool = False,
    ) -> XlsxParsePlan:
        features = XlsxFeature.COMMENTS | XlsxFeature.HYPERLINKS if annotations else XlsxFeature(0)
        return cls(ParsePurpose.RENDER, "plain", features, frozenset((sheet_name,)), window, columns, annotations)

    @classmethod
    def search(cls, kind: str | None, sheets: list[str] | None) -> XlsxParsePlan:
        features = XlsxFeature(0)
        if kind in {None, "formula"}:
            features |= XlsxFeature.FORMULAS
        if kind in {None, "comment"}:
            features |= XlsxFeature.COMMENTS
        if kind in {None, "hyperlink"}:
            features |= XlsxFeature.HYPERLINKS
        if kind in {None, "definedName"}:
            features |= XlsxFeature.DEFINED_NAMES
        return cls(
            ParsePurpose.RENDER,
            "plain",
            features,
            frozenset(sheets) if sheets else None,
            display_text=kind in {None, "value"},
            scan_cells=kind != "definedName",
            retain_cells=kind not in {"comment", "hyperlink", "definedName"},
            formula_only=kind == "formula",
        )


__all__ = ["XlsxFeature", "XlsxParsePlan"]
