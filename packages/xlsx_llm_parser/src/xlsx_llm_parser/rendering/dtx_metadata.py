"""Dtx metadata."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.doctokens_xml import append

from .._utils import col_letter
from ..models import ParsedWorkbook, SheetInfo, WorkbookMetadata


def _append_workbook_metadata(parent: ET.Element, workbook: ParsedWorkbook, density: str) -> None:
    metadata = workbook["metadata"]
    if density not in {"structural", "semantic"}:
        return
    defined = [item for item in metadata.get("defined_names", []) if not item.get("hidden") and item.get("scopeSheet") is None]
    if defined:
        group = append(parent, "defined-names")
        for item in defined:
            append(group, "defined-name", item["ref"], name=item["name"])
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
    if sheet.get("filter_range"):
        filter_node = append(parent, "filter", ref=sheet["filter_range"])
        for condition in sheet.get("filter_cols", []):
            attrs: dict[str, object] = {"column": condition.get("col"), "type": condition.get("type")}
            for old, new in (
                ("values", "values"),
                ("calendarType", "calendar_type"),
                ("operator", "operator"),
                ("value", "value"),
                ("value2", "value2"),
                ("rank", "rank"),
                ("filterValue", "filter_value"),
                ("iconSet", "icon_set"),
                ("dxfId", "dxf_id"),
                ("iconId", "icon_id"),
            ):
                value = condition.get(old)
                if value not in (None, "", []):
                    attrs[new] = ",".join(value) if old == "values" and isinstance(value, list) else value
            for old, new in (
                ("blank", "blank"),
                ("and", "and"),
                ("top", "top"),
                ("percent", "percent"),
                ("cellColor", "cell_color"),
            ):
                if condition.get(old):
                    attrs[new] = True
            if "cellColor" in condition:
                attrs["cell_color"] = bool(condition["cellColor"])
            if date_groups := condition.get("dateGroup"):
                attrs["groups"] = ";".join(
                    ":".join(f"{key}={value}" for key, value in sorted(group.items())) for group in date_groups
                )
            append(filter_node, "condition", **attrs)
    for validation in sheet.get("data_validations", []):
        append(parent, "data-validation", ref=validation.get("ranges"), type=validation.get("type"))
    _append_conditional_formats(parent, sheet, density)
    for image in sheet.get("images", []):
        append(parent, "img", id=image.get("id"), ref=image.get("ref"))
    for chart in sheet.get("charts", []):
        append(
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
            columns=",".join(table.get("columns", [])) if density == "semantic" else None,
            totals_row=True if density == "semantic" and table.get("totalsRow") else None,
        )


def _append_conditional_formats(parent: ET.Element, sheet: SheetInfo, density: str) -> None:
    for conditional_format in sheet.get("conditional_formats", []):
        container = append(parent, "conditional-format", ref=conditional_format.get("ranges"))
        attrs: dict[str, object] = {
            "type": conditional_format.get("ruleType"),
            "priority": conditional_format.get("priority", 0),
            "operator": conditional_format.get("operator"),
            "text": conditional_format.get("text"),
            "dxf": conditional_format.get("dxfId"),
            "style": conditional_format.get("dxfStyle"),
            "stop_if_true": True if conditional_format.get("stopIfTrue") else None,
            "rank": conditional_format.get("rank"),
            "percent": True if conditional_format.get("percent") else None,
            "format": conditional_format.get("formatKind"),
        }
        formulas = conditional_format.get("formulas", [])
        if len(formulas) == 1:
            attrs["formula"] = formulas[0]
        elif formulas:
            attrs["formulas"] = " | ".join(formulas)
        if density == "semantic" and conditional_format.get("formatDetails"):
            attrs["details"] = _conditional_details(conditional_format["formatDetails"])
        append(container, "rule", **attrs)


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
            fields=_joined(cache.get("fields")) if density == "semantic" else None,
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


def _conditional_details(details: object) -> str:
    if not isinstance(details, dict):
        return ""
    values: list[str] = []
    for key, value in details.items():
        if key in {"stops", "thresholds"} and isinstance(value, list):
            records = [
                ":".join(f"{item_key}={item_value}" for item_key, item_value in item.items())
                for item in value
                if isinstance(item, dict)
            ]
            if records:
                values.append(f"{key}={';'.join(records)}")
            continue
        values.append(f"{key}={value}")
    return ";".join(values)
