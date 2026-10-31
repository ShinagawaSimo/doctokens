"""Saved worksheet filters, without evaluating visible rows."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....model.rules import FilterColumn
from ..styles.index import FormatIndex
from .rule_values import boolean
from .rule_values import integer as _safe_int
from .sheet_types import NS_S


def _parse_auto_filter_element(auto_filter: ET.Element, formats: FormatIndex | None) -> tuple[str, list[FilterColumn]]:
    """Parse one completed ``autoFilter`` element from the primary scan."""
    filter_range = auto_filter.get("ref", "")
    filter_cols: list[FilterColumn] = []
    for filter_column in auto_filter.findall(f"{{{NS_S}}}filterColumn"):
        column_id = _safe_int(filter_column.get("colId"), 0)
        filter_cols.extend(_parse_filter_column(column_id, filter_column, formats))
    return filter_range, filter_cols


def _parse_filter_column(column_id: int, element: ET.Element, formats: FormatIndex | None) -> list[FilterColumn]:
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
        if boolean(filters.get("blank")):
            item["blank"] = True
        if (calendar_type := filters.get("calendarType")) and calendar_type != "none":
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
            if index == 0 and boolean(custom.get("and")):
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
            "top": boolean(top10.get("top"), True),
            "percent": boolean(top10.get("percent")),
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
            "cellColor": boolean(color.get("cellColor"), True),
        }
        if formats is not None and (dxf_id := color.get("dxfId")) is not None:
            style = formats.differential_style(_safe_int(dxf_id, -1))
            key = "fill=" if item["cellColor"] else "color="
            if resolved := next((part[len(key) :] for part in style.split() if part.startswith(key)), None):
                item["color"] = resolved
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
        result.append(
            {
                "col": column_id,
                "type": "dateGroup",
                "dateGroup": [
                    {
                        key: value
                        for key, value in group.items()
                        if key in {"year", "month", "day", "hour", "minute", "second", "dateTimeGrouping"}
                    }
                    for group in date_group
                ],
            }
        )
    return result
