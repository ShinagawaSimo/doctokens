"""Density projection of saved worksheet rules, without rule evaluation."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.output.xml import append

from ..model.workbook import SheetInfo


def append_rules(parent: ET.Element, sheet: SheetInfo, density: str) -> None:
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
                ("color", "color"),
                ("iconId", "icon_id"),
            ):
                value = condition.get(old)
                if value not in (None, "", []):
                    attrs[new] = ",".join(value) if old == "values" and isinstance(value, list) else value
            for key in ("blank", "and", "percent"):
                if condition.get(key):
                    attrs[key] = True
            if condition.get("top") is False:
                attrs["top"] = False
            if "cellColor" in condition:
                attrs["cell_color"] = bool(condition["cellColor"])
            if date_groups := condition.get("dateGroup"):
                attrs["groups"] = ";".join(
                    ":".join(f"{key}={value}" for key, value in sorted(group.items())) for group in date_groups
                )
            append(filter_node, "condition", **attrs)
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
        formulas = rule.get("formulas", [])
        if len(formulas) == 1:
            attrs["formula"] = formulas[0]
        elif formulas:
            attrs["formulas"] = " | ".join(formulas)
        if density == "semantic":
            attrs["style"] = rule.get("dxfStyle")
            if rule.get("formatDetails"):
                attrs["details"] = _conditional_details(rule["formatDetails"])
        node = append(container, "rule", **attrs)
        if rule.get("unparsed"):
            append(node, "unsupported", type="conditional-format")


def _conditional_details(details: object) -> str:
    if not isinstance(details, dict):
        return ""
    values: list[str] = []
    for key, value in details.items():
        if isinstance(value, list):
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
