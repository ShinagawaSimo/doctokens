"""Dtx content."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.ooxml.charts.axes import append_chart_axes
from doctokens_core.ooxml.charts.rendering import append_annotations, append_plots
from doctokens_core.output.xml import append, text

from ..model import InlineObject, OcrResultRecord
from .common.ocr import ocr_text


def _append_chart(parent: ET.Element, chart: InlineObject) -> None:
    attrs: dict[str, object] = {
        "id": chart.get("id"),
        "type": chart.get("chartType", "?"),
        "title": chart.get("title"),
        "series": chart.get("seriesCount", 0),
        "truncated": True,
    }
    series = chart.get("series") or []
    categories = [str(item) for item in (series[0].get("categories", []) if series else [])]
    names = [str(item.get("name")) for item in series if item.get("name")]
    if categories:
        attrs["categories"] = ",".join(categories[:8])
    if names:
        attrs["names"] = ",".join(names)
    node = append(parent, "chart", **attrs)
    append_chart_axes(node, chart.get("axes", []))
    append_plots(node, chart.get("plots", []))
    for ordinal, item in enumerate(series[:8]):
        child = append(
            node,
            "series",
            index=item.get("index", ordinal),
            name=item.get("name"),
            plot=item.get("plotIndex"),
            axes=" ".join(item.get("axis_ids", [])) or None,
        )
        append_annotations(child, item.get("labels", []), item.get("label_options", {}), item.get("trendlines", []), preview=True)
        arrays = [
            ("category", item.get("categories", [])),
            ("value", item.get("values", [])),
            ("x", item.get("xValues", [])),
            ("y", item.get("yValues", [])),
            ("bubbleSize", item.get("bubbleSizes", [])),
        ]
        for index in range(min(8, max((len(values) for _, values in arrays), default=0))):
            append(child, "point", index=index, **{key: values[index] for key, values in arrays if index < len(values)})


def _append_smartart(parent: ET.Element, smartart: InlineObject) -> None:
    node = append(
        parent,
        "smartart",
        id=smartart.get("id"),
        type=smartart.get("layoutType"),
        nodes=smartart.get("nodeCount", 0),
        links=smartart.get("linkCount", 0),
        truncated=True if "nodes" not in smartart else None,
        incomplete=True if smartart.get("rawLinkCount", 0) > smartart.get("linkCount", 0) else None,
    )
    for index, item in enumerate(smartart.get("nodes", []), start=1):
        append(node, "node", item["text"], id=index, kind=item.get("kind"))
    for edge in smartart.get("links", []):
        append(node, "link", **{"from": edge["from"], "to": edge["to"], "kind": edge.get("kind")})


def _append_ocr(parent: ET.Element, asset_id: str | None, results: dict[str, OcrResultRecord]) -> None:
    if not asset_id or asset_id not in results:
        return
    result = results[asset_id]
    recognized = ocr_text(result)
    if recognized:
        append(parent, "ocr-text", recognized, id=asset_id)
    elif isinstance(result, dict) and result.get("status") == "empty":
        append(parent, "ocr-text", id=asset_id, empty=True)
    else:
        append(parent, "ocr-text", id=asset_id, error=True)


def _append_text_with_breaks(parent: ET.Element, value: str) -> None:
    fragments = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line_index, line in enumerate(fragments):
        tab_fragments = line.split("\t")
        for tab_index, tab_fragment in enumerate(tab_fragments):
            text(parent, tab_fragment)
            if tab_index < len(tab_fragments) - 1:
                append(parent, "tab")
        if line_index < len(fragments) - 1:
            append(parent, "br")
