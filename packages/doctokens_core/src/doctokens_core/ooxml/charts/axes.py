"""Read and serialize explicit ChartML axis labels, units and saved scales."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ...output.xml import append
from .models import ChartInfo
from .semantics import saved_text

_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_CX = "{http://schemas.microsoft.com/office/drawing/2014/chartex}"
READING_AXIS_FIELDS = frozenset(
    {
        "id",
        "kind",
        "cross_axis",
        "title",
        "num_format",
        "minimum",
        "maximum",
        "log_base",
        "orientation",
        "display_unit",
        "custom_unit",
    }
)
_DISPLAY_UNITS = {
    "hundreds",
    "thousands",
    "tenThousands",
    "hundredThousands",
    "millions",
    "tenMillions",
    "hundredMillions",
    "billions",
    "trillions",
    "percentage",
}


def attach_chart_axes(chart: ChartInfo, root: ET.Element) -> None:
    """Attach reading axes and rewrite all explicit references once per chart."""
    axes = _chartex_axes(root) if root.tag == _CX + "chartSpace" else _chartml_axes(root)
    identifiers: dict[str, str] = {}
    ambiguous: set[str] = set()
    for index, axis in enumerate(axes, 1):
        source_id = axis.pop("id", "").strip()
        axis["id"] = f"axis{index}"
        if source_id:
            if source_id in identifiers:
                ambiguous.add(source_id)
            identifiers[source_id] = axis["id"]
    for source_id in ambiguous:
        identifiers.pop(source_id)
    for axis in axes:
        target = axis.pop("cross_axis", "").strip()
        if target in identifiers:
            axis["cross_axis"] = identifiers[target]
    for members in (chart.get("plots", []), chart.get("series", [])):
        for member in members:
            sources = member.pop("axis_ids", [])
            references = [identifiers[source.strip()] for source in sources if source.strip() in identifiers]
            if references:
                member["axis_ids"] = references
    if axes:
        chart["axes"] = axes


def _chartml_axes(root: ET.Element) -> list[dict[str, str]]:
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
            ("minimum", "scaling/min"),
            ("maximum", "scaling/max"),
            ("log_base", "scaling/logBase"),
            ("orientation", "scaling/orientation"),
            ("display_unit", "dispUnits/builtInUnit"),
            ("custom_unit", "dispUnits/custUnit"),
        ):
            child = node.find("/".join(_C + item for item in path.split("/")))
            if child is not None and (value := child.get("val")) and value.strip() and value != "auto":
                if field == "orientation" and value != "maxMin":
                    continue
                if field == "display_unit" and value not in _DISPLAY_UNITS:
                    continue
                axis[field] = value
        title = node.find(_C + "title")
        if title is not None:
            text = "".join(item.text or "" for item in title.iter(_A + "t"))
            if not text:
                text = "".join(item.text or "" for item in title.iter(_C + "v"))
            if text:
                axis["title"] = text
        fmt = node.find(_C + "numFmt")
        if fmt is not None and (code := fmt.get("formatCode")) and code.strip() and code.strip().casefold() != "general":
            axis["num_format"] = code
        axes.append(axis)
    return axes


def _chartex_axes(root: ET.Element) -> list[dict[str, str]]:
    area = root.find(_CX + "chart/" + _CX + "plotArea")
    if area is None:
        return []
    axes = []
    for source in area.findall(_CX + "axis"):
        axis = {"kind": "axis"}
        if source.get("id"):
            axis["id"] = source.get("id", "")
        title = source.find(_CX + "title/" + _CX + "tx")
        if value := saved_text(title, _CX):
            axis["title"] = value
        scaling = source.find(_CX + "valScaling")
        if scaling is None:
            scaling = source.find(_CX + "catScaling")
        if scaling is not None:
            axis["kind"] = "valAx" if scaling.tag == _CX + "valScaling" else "catAx"
            if scaling.tag == _CX + "valScaling":
                for source_key, field in (("min", "minimum"), ("max", "maximum")):
                    if (limit := scaling.get(source_key)) and limit.strip() and limit != "auto":
                        axis[field] = limit
        fmt = source.find(_CX + "numFmt")
        if fmt is not None and (code := fmt.get("formatCode")) and code.strip() and code.strip().casefold() != "general":
            axis["num_format"] = code
        units = source.find(_CX + "units")
        if units is not None and units.get("unit") in _DISPLAY_UNITS:
            axis["display_unit"] = units.get("unit", "")
        axes.append(axis)
    return axes


def append_chart_axes(parent: ET.Element, axes: list[dict[str, str]]) -> None:
    for axis in axes:
        append(parent, "axis", **{key: value for key, value in axis.items() if key in READING_AXIS_FIELDS})
