"""Read document defaults, typed styles, and table conditional property sets."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..model import ParseWarning, StyleRecord, append_warning
from .formatting import normalize_hex_color, parse_paragraph_alignment, parse_paragraph_borders, parse_run_format
from .namespaces import attr, first_child, qualified_name
from .outline import parse_outline_level
from .package import PackageReader
from .styles import StyleMap


def _properties(
    record: StyleRecord,
    paragraph: ET.Element | None,
    run: ET.Element | None,
    table: ET.Element | None,
    cell: ET.Element | None,
    warnings: list[ParseWarning],
    formatting: bool,
) -> None:
    record.outline_level = parse_outline_level(paragraph, warnings, part="word/styles.xml")
    num_pr = first_child(paragraph, "w", "numPr")
    record.numbering_num_id = attr(first_child(num_pr, "w", "numId"), "w", "val")
    value = attr(first_child(num_pr, "w", "ilvl"), "w", "val")
    if value is not None:
        try:
            record.numbering_level = int(value)
        except ValueError:
            record.numbering_level = 0
            append_warning(
                warnings, "INVALID_STYLE_NUMBERING_LEVEL", f"Invalid numbering level {value!r}", part="word/styles.xml"
            )
    if formatting:
        record.alignment = parse_paragraph_alignment(paragraph)
        record.borders = parse_paragraph_borders(paragraph)
        record.run_format = parse_run_format(run)
        shading = first_child(cell, "w", "shd")
        if shading is None:
            shading = first_child(table, "w", "shd")
        fill = attr(shading, "w", "fill")
        if fill is not None:
            record.cell_background = normalize_hex_color(fill) or ""
        if attr(shading, "w", "val") == "nil":
            record.cell_background = ""
    for name, field in (("tblStyleRowBandSize", "row_band_size"), ("tblStyleColBandSize", "column_band_size")):
        value = attr(first_child(table, "w", name), "w", "val")
        if value is not None:
            try:
                size = int(value)
                if size < 1:
                    raise ValueError
                setattr(record, field, size)
            except ValueError:
                append_warning(warnings, "INVALID_TABLE_BAND_SIZE", f"Invalid table band size {value!r}", part="word/styles.xml")


class StylesParser:
    def __init__(
        self, package: PackageReader, warnings: list[ParseWarning], *, include_character_formatting: bool = True
    ) -> None:
        self.package = package
        self.warnings = warnings
        self.formatting = include_character_formatting

    def parse(self) -> StyleMap:
        if not self.package.exists("word/styles.xml"):
            append_warning(
                self.warnings,
                "MISSING_STYLES",
                "word/styles.xml is missing; style resolution is limited.",
                part="word/styles.xml",
            )
            return StyleMap({}, self.warnings)
        root = self.package.read_xml("word/styles.xml")
        defaults = StyleRecord(style_id="")
        doc_defaults = first_child(root, "w", "docDefaults")
        _properties(
            defaults,
            first_child(first_child(doc_defaults, "w", "pPrDefault"), "w", "pPr"),
            first_child(first_child(doc_defaults, "w", "rPrDefault"), "w", "rPr"),
            None,
            None,
            self.warnings,
            self.formatting,
        )
        records: dict[str, StyleRecord] = {}
        for style in root.findall(qualified_name("w", "style")):
            style_id = attr(style, "w", "styleId")
            if not style_id:
                continue
            record = StyleRecord(
                style_id=style_id,
                type=attr(style, "w", "type") or "paragraph",
                is_default=(attr(style, "w", "default") or "").lower() in {"1", "true", "on"},
                is_custom=(attr(style, "w", "customStyle") or "").lower() in {"1", "true", "on"},
            )
            for name, field in (("name", "name"), ("basedOn", "based_on"), ("link", "link"), ("next", "next")):
                setattr(record, field, attr(first_child(style, "w", name), "w", "val"))
            _properties(
                record,
                first_child(style, "w", "pPr"),
                first_child(style, "w", "rPr"),
                first_child(style, "w", "tblPr"),
                first_child(style, "w", "tcPr"),
                self.warnings,
                self.formatting,
            )
            for region in style.findall(qualified_name("w", "tblStylePr")):
                kind = attr(region, "w", "type")
                if kind:
                    props = StyleRecord(style_id="")
                    _properties(
                        props,
                        first_child(region, "w", "pPr"),
                        first_child(region, "w", "rPr"),
                        first_child(region, "w", "tblPr"),
                        first_child(region, "w", "tcPr"),
                        self.warnings,
                        self.formatting,
                    )
                    record.table_regions[kind] = props
            records[style_id] = record
        index = StyleMap(records, self.warnings, defaults=defaults)
        for record in records.values():
            if record.type == "paragraph":
                record.resolved_heading_level = index.resolve_heading_level(record.style_id)
        return index
