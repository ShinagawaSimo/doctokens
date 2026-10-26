"""resources."""

from __future__ import annotations

from doctokens_core.contracts.models import ResourceDescriptor
from doctokens_core.ooxml.charts.axes import append_chart_axes
from doctokens_core.output.resources import resource_document
from doctokens_core.output.xml import append, element

from ..model.workbook import DrawingChart, ParsedWorkbook


def _resource_descriptors(workbook: ParsedWorkbook) -> tuple[ResourceDescriptor, ...]:
    descriptors: list[ResourceDescriptor] = []
    for sheet in workbook["sheets"]:
        descriptors.extend(
            ResourceDescriptor(
                id=image["id"],
                kind="image",
                source="embedded",
                locator=f"{sheet['name']}!{image.get('ref', '')}",
                part=image.get("part"),
            )
            for image in sheet.get("images", [])
        )
        descriptors.extend(
            ResourceDescriptor(
                id=chart["id"],
                kind="chart",
                source="embedded",
                locator=f"{sheet['name']}!{chart.get('ref', '')}",
                part=chart.get("part"),
            )
            for chart in sheet.get("charts", [])
        )
        descriptors.extend(
            ResourceDescriptor(
                id=pivot["id"],
                kind="pivot_table",
                source="embedded",
                locator=f"{sheet['name']}!{pivot.get('ref', '')}",
            )
            for pivot in sheet.get("pivot_tables", [])
        )
        descriptors.extend(
            ResourceDescriptor(
                id=table["id"],
                kind="table",
                source="embedded",
                locator=f"{sheet['name']}!{table.get('ref', '')}",
            )
            for table in sheet.get("tables", [])
        )
    return tuple(descriptors)


def _render_chart_resource(chart: DrawingChart) -> str:
    node = element(
        "chart",
        id=chart["id"],
        ref=chart["ref"],
        type=chart.get("type", "?"),
        plots=",".join(chart["plotTypes"]) if chart.get("plotTypes") else None,
        series=chart.get("series_count", 0),
        title=chart.get("title") or None,
    )
    append_chart_axes(node, chart.get("axes", []))
    for series in chart.get("series", []):
        child = append(
            node,
            "series",
            index=series.get("index", 0),
            name=series.get("name") or None,
            min=series.get("min"),
            max=series.get("max"),
            type=series.get("chartType") if chart.get("type") == "combination" else None,
            bubbleSizes=",".join(series["bubbleSizes"]) if series.get("bubbleSizes") else None,
            hidden=True if series.get("hidden") else None,
        )
        for point in series.get("points", []):
            append(
                child,
                "point",
                **{name: point[name] for name in ("category", "value", "x", "y", "bubbleSize") if point.get(name, "")},
            )
    return resource_document("xlsx", node)
