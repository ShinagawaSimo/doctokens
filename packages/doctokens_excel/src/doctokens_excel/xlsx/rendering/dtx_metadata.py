"""Dtx metadata."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.ooxml.charts.axes import append_chart_axes
from doctokens_core.ooxml.charts.rendering import append_plots
from doctokens_core.output.xml import append

from ..model.coordinates import col_letter
from ..model.workbook import ParsedWorkbook, SheetInfo, WorkbookMetadata
from .dtx_rules import append_rules


def _append_workbook_metadata(parent: ET.Element, workbook: ParsedWorkbook, density: str, *, range_context: bool = False) -> None:
    metadata = workbook["metadata"]
    if density not in {"structural", "semantic"}:
        return
    defined = [
        item
        for item in metadata.get("defined_names", [])
        if range_context or (not item.get("hidden") and item.get("scopeSheet") is None)
    ]
    if defined:
        group = append(parent, "defined-names")
        for item in defined:
            append(group, "defined-name", item["ref"], name=item["name"], sheet=item.get("scopeSheet") if range_context else None)
    external_links = metadata.get("external_links", [])
    if external_links:
        group = append(parent, "external-links")
        for target in external_links:
            append(group, "external-link", target=target)
    _append_pivot_context(parent, metadata, density)


def _append_sheet_metadata(
    parent: ET.Element,
    sheet: SheetInfo,
    workbook: ParsedWorkbook,
    density: str,
    emit_globals: bool,
) -> None:
    if density not in {"structural", "semantic"}:
        return
    for first, last in sheet.get("hidden_cols", []):
        ref = col_letter(first) if first == last else f"{col_letter(first)}:{col_letter(last)}"
        append(parent, "columns", ref=ref, hidden=True)
    if sheet.get("sheet_protection"):
        append(parent, "sheet-protection")
    for defined_name in workbook["metadata"].get("defined_names", []):
        if defined_name.get("hidden") or defined_name["name"].startswith("_xlnm."):
            continue
        scope = defined_name.get("scopeSheet")
        if scope == sheet["name"]:
            append(parent, "defined-name", defined_name["ref"], name=defined_name["name"])
        elif scope is None and emit_globals:
            # Global definitions live once at root and are not duplicated here.
            continue
    append_rules(parent, sheet, density)
    for image in sheet.get("images", []):
        node = append(
            parent,
            "img",
            id=image.get("id"),
            ref=image.get("ref"),
            alt=image.get("alt") or None,
            title=image.get("title"),
            group=image.get("group"),
            href=image.get("href"),
            link=image.get("link"),
        )
        if image.get("unparsed"):
            append(node, "unsupported", type="image")
    for chart in sheet.get("charts", []):
        chart_node = append(
            parent,
            "chart",
            id=chart.get("id"),
            ref=chart.get("ref"),
            type=chart.get("type", "?"),
            plots=",".join(chart.get("plotTypes", [])) or None,
            series=chart.get("series_count", 0),
            names=",".join(_chart_names(chart)) or None,
            title=chart.get("title"),
            truncated=True,
            group=chart.get("group"),
        )
        append_chart_axes(chart_node, chart.get("axes", []))
        append_plots(chart_node, chart.get("plots", []))
        if chart.get("unparsed"):
            append(chart_node, "unsupported", type="chart")
    for shape in sheet.get("drawing_shapes", []):
        attrs = {
            "id": shape.get("id"),
            "ref": shape.get("ref") or None,
            "group": shape.get("group"),
            "alt": shape.get("alt"),
            "title": shape.get("title"),
            "link": shape.get("link"),
        }
        if shape["kind"] == "unsupported":
            append(parent, "unsupported", type="drawing", source=shape.get("name"), **attrs)
        elif shape["kind"] == "group":
            append(parent, "drawing-group", name=shape.get("name") or None, **attrs)
        elif shape.get("paragraphs"):
            node = append(
                parent,
                "textbox",
                kind="connector" if shape.get("kind") == "connector" else None,
                from_shape=shape.get("fromShape"),
                to_shape=shape.get("toShape"),
                **attrs,
            )
            for paragraph in shape["paragraphs"]:
                append(node, "p", paragraph)
        else:
            append(
                parent, "shape", kind=shape.get("kind"), from_shape=shape.get("fromShape"), to_shape=shape.get("toShape"), **attrs
            )
    for pivot in sheet.get("pivot_tables", []):
        pivot_attrs: dict[str, object] = {
            "id": pivot.get("id"),
            "name": pivot.get("name"),
            "ref": pivot.get("ref"),
            "source_sheet": pivot.get("sourceSheet"),
            "source_ref": pivot.get("sourceRef"),
        }
        if density == "semantic":
            for old, new in (
                ("rowFields", "rows"),
                ("columnFields", "columns"),
                ("pageFields", "pages"),
                ("dataFields", "values"),
                ("filters", "filters"),
            ):
                values = pivot.get(old)
                if values:
                    pivot_attrs[new] = _joined(values)
        append(parent, "pivot-table", **pivot_attrs)
    for table in sheet.get("tables", []):
        append(
            parent,
            "table-summary",
            id=table.get("id"),
            name=table.get("name"),
            ref=table.get("ref"),
            columns=(",".join(table.get("columns", [])) or None) if density == "semantic" else None,
            totals_row=True if density == "semantic" and table.get("totalsRow") else None,
        )


def _append_pivot_context(parent: ET.Element, metadata: WorkbookMetadata, density: str) -> None:
    for cache in cast(list[dict[str, object]], metadata.get("pivot_caches", [])):
        append(
            parent,
            "pivot-cache",
            id=cache.get("id"),
            cache_id=cache.get("cacheId"),
            sheet=cache.get("sourceSheet"),
            ref=cache.get("sourceRef"),
            refresh_on_load=True if cache.get("refreshOnLoad") else None,
            fields=(_joined(cache.get("fields")) or None) if density == "semantic" else None,
        )
    for slicer in cast(list[dict[str, object]], metadata.get("slicers", [])):
        append(
            parent,
            "slicer",
            id=slicer.get("id"),
            name=slicer.get("name"),
            source=slicer.get("sourceName"),
            cache_id=slicer.get("cacheId"),
        )
    for timeline in cast(list[dict[str, object]], metadata.get("timelines", [])):
        append(
            parent,
            "timeline",
            id=timeline.get("id"),
            name=timeline.get("name"),
            source=timeline.get("sourceName"),
            level=timeline.get("level"),
        )


def _add_protection_attrs(attrs: dict[str, object], value: str) -> None:
    for item in value.split():
        if item == "unlocked":
            attrs["locked"] = False
        elif item == "formulaHidden":
            attrs["formula_hidden"] = True


def _chart_names(chart: object) -> list[str]:
    if not isinstance(chart, dict):
        return []
    return [str(item.get("name")) for item in chart.get("series", []) if item.get("name")]


def _joined(value: object) -> str:
    return ",".join(str(item) for item in value) if isinstance(value, list) else ""
