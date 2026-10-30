"""Read and serialize explicit ChartML axis labels, units and saved scales."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ...output.xml import append
from .semantics import saved_text

_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_CX = "{http://schemas.microsoft.com/office/drawing/2014/chartex}"


def parse_chart_axes(root: ET.Element) -> list[dict[str, str]]:
    if root.tag == _CX + "chartSpace":
        return _chartex_axes(root)
    area = root.find(".//" + _C + "plotArea")
    if area is None:
        return []
    axes = []
    for node in area:
        if node.tag not in {_C + kind for kind in ("catAx", "valAx", "dateAx", "serAx")}:
            continue
        axis = {"kind": node.tag.removeprefix(_C)}
        for field, path in (
            ("id", "axId"),
            ("cross_axis", "crossAx"),
            ("position", "axPos"),
            ("minimum", "scaling/min"),
            ("maximum", "scaling/max"),
            ("log_base", "scaling/logBase"),
            ("orientation", "scaling/orientation"),
            ("display_unit", "dispUnits/builtInUnit"),
            ("custom_unit", "dispUnits/custUnit"),
        ):
            child = node.find("/".join(_C + item for item in path.split("/")))
            if child is not None and child.get("val") is not None:
                axis[field] = child.get("val", "")
        title = node.find(_C + "title")
        if title is not None:
            text = "".join(item.text or "" for item in title.iter(_A + "t"))
            if not text:
                text = "".join(item.text or "" for item in title.iter(_C + "v"))
            if text:
                axis["title"] = text
        fmt = node.find(_C + "numFmt")
        if fmt is not None and fmt.get("formatCode") is not None:
            axis["num_format"] = fmt.get("formatCode", "")
        axes.append(axis)
    return axes


def _chartex_axes(root: ET.Element) -> list[dict[str, str]]:
    area = root.find(_CX + "chart/" + _CX + "plotArea")
    if area is None:
        return []
    axes = []
    for source in area.findall(_CX + "axis"):
        axis = {"kind": "axis", **source.attrib}
        title = source.find(_CX + "title/" + _CX + "tx")
        if value := saved_text(title, _CX):
            axis["title"] = value
        scaling = source.find(_CX + "valScaling")
        if scaling is None:
            scaling = source.find(_CX + "catScaling")
        if scaling is not None:
            axis["kind"] = "valAx" if scaling.tag == _CX + "valScaling" else "catAx"
            for key, value in scaling.attrib.items():
                if value != "auto":
                    axis[{"min": "minimum", "max": "maximum"}.get(key, key)] = value
        fmt = source.find(_CX + "numFmt")
        if fmt is not None and fmt.get("formatCode"):
            axis["num_format"] = fmt.get("formatCode", "")
        units = source.find(_CX + "units")
        if units is not None:
            axis.update(units.attrib)
        axes.append(axis)
    return axes


def append_chart_axes(parent: ET.Element, axes: list[dict[str, str]]) -> None:
    for axis in axes:
        append(parent, "axis", **axis)
