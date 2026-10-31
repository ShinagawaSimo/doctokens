"""Saved visual conditional-format thresholds and appearance declarations."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.xml import local_name

from ..styles.colors import SpreadsheetColors
from .rule_values import X14, XM

_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def visual_details(rule: ET.Element, colors: SpreadsheetColors) -> tuple[str, dict[str, object]] | None:
    """Capture visual rule semantics without evaluating colors or thresholds."""
    for child in rule:
        if not child.tag.startswith((f"{{{_S}}}", f"{{{X14}}}")):
            continue
        name = local_name(child.tag)
        if name == "colorScale":
            stops: list[dict[str, str]] = []
            cfvos = [item for item in child if local_name(item.tag) == "cfvo"]
            color_nodes = [item for item in child if local_name(item.tag) == "color"]
            for index, cfvo in enumerate(cfvos):
                stop = _threshold(cfvo)
                if index < len(color_nodes) and (color := colors.resolve(color_nodes[index])):
                    stop["color"] = f"#{color}"
                stops.append(stop)
            return "colorScale", {"stops": stops}
        if name == "dataBar":
            details: dict[str, object] = {}
            if child.get("showValue") in {"0", "false"}:
                details["showValue"] = "false"
            color = next(
                (colors.resolve(item) for item in child if local_name(item.tag) in {"color", "fillColor"}),
                None,
            )
            if color:
                details["color"] = f"#{color}"
            for item in child:
                name = local_name(item.tag)
                if (
                    name == "negativeFillColor"
                    and child.get("negativeBarColorSameAsPositive") not in {"1", "true"}
                    and (color := colors.resolve(item))
                ):
                    details[name] = f"#{color}"
            thresholds = _format_thresholds(child)
            if thresholds:
                details["thresholds"] = thresholds
            return "dataBar", details
        if name == "iconSet":
            icon_details: dict[str, object] = {"iconSet": child.get("iconSet", "3TrafficLights1")}
            if child.get("showValue") in {"0", "false"}:
                icon_details["showValue"] = "false"
            if child.get("reverse") in {"1", "true"}:
                icon_details["reverse"] = "true"
            thresholds = _format_thresholds(child)
            if thresholds:
                icon_details["thresholds"] = thresholds
            icons = [
                {key: value for key, value in node.attrib.items() if key in {"iconSet", "iconId"}}
                for node in child
                if local_name(node.tag) == "cfIcon"
            ]
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
    if result.get("gte") in {"1", "true"}:
        result.pop("gte")
    elif result.get("gte") in {"0", "false"}:
        result["gte"] = "false"
    if result.get("type") in {"min", "max", "autoMin", "autoMax"}:
        result.pop("val", None)
    return result
