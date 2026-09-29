"""Rules."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.xml import local_name

from ....models import (
    ConditionalFormat,
    DataValidation,
    FilterColumn,
)
from ..styles.index import FormatIndex
from .sheet_types import NS_S


def _parse_auto_filter_element(auto_filter: ET.Element) -> tuple[str, list[FilterColumn]]:
    """Parse one completed ``autoFilter`` element from the primary scan."""
    filter_range = auto_filter.get("ref", "")
    filter_cols: list[FilterColumn] = []
    for filter_column in auto_filter.findall(f"{{{NS_S}}}filterColumn"):
        column_id = _safe_int(filter_column.get("colId"), 0)
        filter_cols.extend(_parse_filter_column(column_id, filter_column))
    return filter_range, filter_cols


def _parse_filter_column(column_id: int, element: ET.Element) -> list[FilterColumn]:
    """Read every Excel filter form without evaluating the resulting row set."""
    result: list[FilterColumn] = []
    filters = element.find(f"{{{NS_S}}}filters")
    date_group: list[dict[str, str]] = []
    if filters is not None:
        item: FilterColumn = {"col": column_id, "type": "values"}
        values = [child.get("val", "") for child in filters.findall(f"{{{NS_S}}}filter") if child.get("val")]
        date_group.extend(dict(child.attrib) for child in filters.findall(f"{{{NS_S}}}dateGroupItem"))
        if values:
            item["values"] = values
        if filters.get("blank") == "1":
            item["blank"] = True
        if calendar_type := filters.get("calendarType"):
            item["calendarType"] = calendar_type
        if values or item.get("blank") or item.get("calendarType"):
            result.append(item)

    custom = element.find(f"{{{NS_S}}}customFilters")
    if custom is not None:
        for index, rule in enumerate(custom.findall(f"{{{NS_S}}}customFilter")):
            item = {
                "col": column_id,
                "type": "custom",
                "operator": rule.get("operator", "equal"),
                "value": rule.get("val", ""),
            }
            if index == 0 and custom.get("and") == "1":
                item["and"] = True
            result.append(item)

    dynamic = element.find(f"{{{NS_S}}}dynamicFilter")
    if dynamic is not None:
        item = {"col": column_id, "type": "dynamic", "operator": dynamic.get("type", "")}
        for attr_name in ("val", "maxVal"):
            if attr_value := dynamic.get(attr_name):
                item["value" if attr_name == "val" else "value2"] = attr_value
        result.append(item)

    top10 = element.find(f"{{{NS_S}}}top10")
    if top10 is not None:
        item = {
            "col": column_id,
            "type": "top10",
            "top": top10.get("top", "1") == "1",
            "percent": top10.get("percent", "0") == "1",
            "rank": top10.get("val", ""),
        }
        if filter_value := top10.get("filterVal"):
            item["filterValue"] = filter_value
        result.append(item)

    color = element.find(f"{{{NS_S}}}colorFilter")
    if color is not None:
        item = {
            "col": column_id,
            "type": "color",
            "cellColor": color.get("cellColor", "1") == "1",
        }
        if dxf_id := color.get("dxfId"):
            item["dxfId"] = _safe_int(dxf_id, 0)
        result.append(item)

    icon = element.find(f"{{{NS_S}}}iconFilter")
    if icon is not None:
        item = {"col": column_id, "type": "icon"}
        if icon_set := icon.get("iconSet"):
            item["iconSet"] = icon_set
        if icon_id := icon.get("iconId"):
            item["iconId"] = _safe_int(icon_id, 0)
        result.append(item)

    # A few producers place dateGroupItem directly under filterColumn; accept it
    # in addition to the SpreadsheetML-standard location under filters.
    date_group.extend(dict(child.attrib) for child in element.findall(f"{{{NS_S}}}dateGroupItem"))
    if date_group:
        result.append({"col": column_id, "type": "dateGroup", "dateGroup": date_group})
    return result


def _parse_data_validations_element(validations: ET.Element) -> list[DataValidation]:
    """Parse one completed ``dataValidations`` element."""
    return [
        {
            "ranges": item.get("sqref", ""),
            "type": item.get("type", ""),
            "formula1": item.findtext(f"{{{NS_S}}}formula1", ""),
            "allowBlank": item.get("allowBlank", "1") == "1",
        }
        for item in validations.findall(f"{{{NS_S}}}dataValidation")
    ]


def _parse_conditional_format_element(
    conditional_format: ET.Element,
    format_index: FormatIndex | None,
) -> list[ConditionalFormat]:
    formats: list[ConditionalFormat] = []
    ranges = conditional_format.get("sqref", "")
    for rule in conditional_format.findall(f"{{{NS_S}}}cfRule"):
        item: ConditionalFormat = {
            "ranges": ranges,
            "priority": _safe_int(rule.get("priority"), 0),
            "ruleType": rule.get("type", ""),
            "formulas": [formula.text or "" for formula in rule.findall(f"{{{NS_S}}}formula")],
            "stopIfTrue": rule.get("stopIfTrue", "0") == "1",
        }
        dxf_id = rule.get("dxfId")
        if dxf_id is not None:
            parsed_dxf_id = _safe_int(dxf_id, 0)
            item["dxfId"] = parsed_dxf_id
            if format_index is not None:
                dxf_style = format_index.differential_style(parsed_dxf_id)
                if dxf_style:
                    item["dxfStyle"] = dxf_style
        if operator := rule.get("operator"):
            item["operator"] = operator
        if text := rule.get("text"):
            item["text"] = text
        if rank := rule.get("rank"):
            item["rank"] = _safe_int(rank, 0)
        if rule.get("percent") == "1":
            item["percent"] = True

        detail = _conditional_format_detail(rule)
        if detail is not None:
            item["formatKind"], item["formatDetails"] = detail
        formats.append(item)
    return formats


def _conditional_format_detail(rule: ET.Element) -> tuple[str, dict[str, object]] | None:
    """Capture visual rule semantics without evaluating colors or thresholds."""
    for child in rule:
        name = local_name(child.tag)
        if name == "colorScale":
            stops: list[dict[str, str]] = []
            cfvos = [item for item in child if local_name(item.tag) == "cfvo"]
            colors = [item for item in child if local_name(item.tag) == "color"]
            for index, cfvo in enumerate(cfvos):
                stop = {key: value for key, value in cfvo.attrib.items() if key in {"type", "val", "gte"}}
                if index < len(colors):
                    color = colors[index].get("rgb") or colors[index].get("theme") or colors[index].get("indexed")
                    if color:
                        stop["color"] = color
                stops.append(stop)
            return "colorScale", {"stops": stops}
        if name == "dataBar":
            details: dict[str, object] = {}
            for key in ("minLength", "maxLength", "showValue", "gradient", "border", "direction"):
                value = child.get(key)
                if value is not None:
                    details[key] = value
            color = next(
                (
                    item.get("rgb") or item.get("theme") or item.get("indexed")
                    for item in child
                    if local_name(item.tag) == "color"
                ),
                None,
            )
            if color:
                details["color"] = color
            thresholds = _format_thresholds(child)
            if thresholds:
                details["thresholds"] = thresholds
            return "dataBar", details
        if name == "iconSet":
            icon_details: dict[str, object] = dict(child.attrib)
            thresholds = _format_thresholds(child)
            if thresholds:
                icon_details["thresholds"] = thresholds
            return "iconSet", icon_details
    return None


def _format_thresholds(parent: ET.Element) -> list[dict[str, str]]:
    return [
        {key: value for key, value in item.attrib.items() if key in {"type", "val", "gte"}}
        for item in parent
        if local_name(item.tag) == "cfvo"
    ]


def _safe_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default
