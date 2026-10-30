"""Saved visual conditional-format thresholds and appearance declarations."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.xml import local_name

from .rule_values import X14, XM

_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def visual_details(rule: ET.Element) -> tuple[str, dict[str, object]] | None:
    """Capture visual rule semantics without evaluating colors or thresholds."""
    for child in rule:
        if not child.tag.startswith((f"{{{_S}}}", f"{{{X14}}}")):
            continue
        name = local_name(child.tag)
        if name == "colorScale":
            stops: list[dict[str, str]] = []
            cfvos = [item for item in child if local_name(item.tag) == "cfvo"]
            colors = [item for item in child if local_name(item.tag) == "color"]
            for index, cfvo in enumerate(cfvos):
                stop = _threshold(cfvo)
                if index < len(colors):
                    color = colors[index].get("rgb") or colors[index].get("theme") or colors[index].get("indexed")
                    if color:
                        stop["color"] = color
                stops.append(stop)
            return "colorScale", {"stops": stops}
        if name == "dataBar":
            details: dict[str, object] = {}
            for key in (
                "minLength",
                "maxLength",
                "showValue",
                "gradient",
                "border",
                "direction",
                "negativeBarColorSameAsPositive",
                "negativeBarBorderColorSameAsPositive",
                "axisPosition",
            ):
                value = child.get(key)
                if value is not None:
                    details[key] = value
            color = next(
                (
                    item.get("rgb") or item.get("theme") or item.get("indexed")
                    for item in child
                    if local_name(item.tag) in {"color", "fillColor"}
                ),
                None,
            )
            if color:
                details["color"] = color
            for item in child:
                name = local_name(item.tag)
                if name in {"borderColor", "negativeFillColor", "negativeBorderColor", "axisColor"}:
                    details[name] = item.get("rgb") or item.get("theme") or item.get("indexed") or ""
            thresholds = _format_thresholds(child)
            if thresholds:
                details["thresholds"] = thresholds
            return "dataBar", details
        if name == "iconSet":
            icon_details: dict[str, object] = dict(child.attrib)
            thresholds = _format_thresholds(child)
            if thresholds:
                icon_details["thresholds"] = thresholds
            icons = [dict(node.attrib) for node in child if local_name(node.tag) == "cfIcon"]
            if icons:
                icon_details["icons"] = icons
            return "iconSet", icon_details
    return None


def _format_thresholds(parent: ET.Element) -> list[dict[str, str]]:
    return [_threshold(item) for item in parent if local_name(item.tag) == "cfvo"]


def _threshold(node: ET.Element) -> dict[str, str]:
    result = {key: value for key, value in node.attrib.items() if key in {"type", "val", "gte"}}
    if (formula := node.find(f"{{{XM}}}f")) is not None:
        result["val"] = formula.text or ""
    return result
