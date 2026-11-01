"""Density projection of saved worksheet rules, without rule evaluation."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.output.xml import append

from ..model.rules import VisualDetails
from ..model.workbook import SheetInfo


def append_rules(parent: ET.Element, sheet: SheetInfo, density: str) -> None:
    if sheet.get("filter_range"):
        filter_node = append(parent, "filter", ref=sheet["filter_range"])
        for condition in sheet.get("filter_cols", []):
            attrs: dict[str, object] = {"column": condition.get("col"), "type": condition.get("type")}
            for old, new in (
                ("calendarType", "calendar_type"),
                ("operator", "operator"),
                ("value", "value"),
                ("value2", "value2"),
                ("rank", "rank"),
                ("filterValue", "filter_value"),
                ("iconSet", "icon_set"),
                ("color", "color"),
                ("iconId", "icon_id"),
            ):
                value = condition.get(old)
                if value not in (None, "", []):
                    attrs[new] = value
            for key in ("blank", "and", "percent"):
                if condition.get(key):
                    attrs[key] = True
            if condition.get("top") is False:
                attrs["top"] = False
            if "cellColor" in condition:
                attrs["cell_color"] = bool(condition["cellColor"])
            node = append(filter_node, "condition", **attrs)
            for value in condition.get("values", []):
                append(node, "value", value)
            for group in condition.get("dateGroup", []):
                append(
                    node,
                    "date-group",
                    grouping=group.get("dateTimeGrouping"),
                    **{key: value for key, value in group.items() if key != "dateTimeGrouping"},
                )
    for validation in sheet.get("data_validations", []):
        attrs = {"ref": validation.get("ranges"), "type": validation.get("type")}
        for key in ("formula1", "formula2"):
            attrs[key] = validation.get(key)
        if validation.get("operator") != "between":
            attrs["operator"] = validation.get("operator")
        if validation.get("allowBlank"):
            attrs["allow_blank"] = True
        # This flag determines whether invalid entries trigger an error at all.
        if validation.get("type") != "none" and validation.get("showErrorMessage"):
            attrs["show_error_message"] = True
            attrs["error_style"] = validation.get("errorStyle")
        if density == "semantic":
            for old, new in (
                ("promptTitle", "prompt_title"),
                ("prompt", "prompt"),
                ("errorTitle", "error_title"),
                ("error", "error"),
            ):
                attrs[new] = validation.get(old)
            if (validation.get("promptTitle") or validation.get("prompt")) and validation.get("showInputMessage"):
                attrs["show_input_message"] = True
            if validation.get("type") == "none" and (validation.get("errorTitle") or validation.get("error")):
                attrs["show_error_message"] = True if validation.get("showErrorMessage") else None
        node = append(parent, "data-validation", **attrs)
        if validation.get("unparsed"):
            append(node, "unsupported", type="data-validation")
    _append_conditional_formats(parent, sheet, density)


def _append_conditional_formats(parent: ET.Element, sheet: SheetInfo, density: str) -> None:
    for rule in sheet.get("conditional_formats", []):
        container = append(parent, "conditional-format", ref=rule.get("ranges"))
        priority = rule.get("priority", 0)
        attrs: dict[str, object] = {
            "type": rule.get("ruleType"),
            "priority": priority if priority > 0 else None,
            "operator": rule.get("operator"),
            "text": rule.get("text"),
            "stop_if_true": True if rule.get("stopIfTrue") else None,
            "rank": rule.get("rank"),
            "percent": True if rule.get("percent") else None,
            "bottom": True if rule.get("bottom") else None,
            "above_average": False if rule.get("aboveAverage") is False else None,
            "equal_average": True if rule.get("equalAverage") else None,
            "std_dev": rule.get("stdDev") or None,
            "time_period": rule.get("timePeriod"),
        }
        if rule.get("formatKind") != rule.get("ruleType"):
            attrs["format"] = rule.get("formatKind")
        node = append(container, "rule", **attrs)
        for formula in rule.get("formulas", []):
            append(node, "formula", formula)
        if density == "semantic":
            if rule.get("dxfStyle"):
                append(node, "style", **rule["dxfStyle"])
            if rule.get("formatDetails"):
                _append_visual(node, rule.get("formatKind", ""), rule["formatDetails"])
        if rule.get("unparsed"):
            append(node, "unsupported", type="conditional-format")


def _append_visual(parent: ET.Element, kind: str, details: VisualDetails) -> None:
    if kind == "colorScale":
        node = append(parent, "color-scale")
    elif kind == "dataBar":
        node = append(
            parent,
            "data-bar",
            color=details.get("color"),
            negative_fill_color=details.get("negativeFillColor"),
            show_value=details.get("showValue"),
        )
    elif kind == "iconSet":
        node = append(
            parent,
            "icon-set",
            name=details.get("iconSet"),
            reverse=details.get("reverse"),
            show_value=details.get("showValue"),
        )
    else:
        return
    stops = details.get("stops", []) if kind == "colorScale" else details.get("thresholds", [])
    for stop in stops:
        append(
            node,
            "stop" if kind == "colorScale" else "threshold",
            type=stop.get("type"),
            value=stop.get("val"),
            gte=stop.get("gte"),
            color=stop.get("color"),
        )
    if kind == "iconSet":
        for icon in details.get("icons", []):
            append(node, "icon", set=icon.get("iconSet"), id=icon.get("iconId"))
