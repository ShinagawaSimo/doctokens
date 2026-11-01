"""resources."""

from __future__ import annotations

from doctokens_core.contracts.models import ResourceDescriptor
from doctokens_core.ooxml.charts.axes import append_chart_axes
from doctokens_core.ooxml.charts.rendering import append_annotations, append_plots, append_points
from doctokens_core.output.resources import resource_document
from doctokens_core.output.xml import append, element

from ..model.drawing import DrawingChart
from ..model.workbook import ParsedWorkbook


def _resource_descriptors(workbook: ParsedWorkbook) -> tuple[ResourceDescriptor, ...]:
    descriptors: list[ResourceDescriptor] = []
    for sheet in workbook["sheets"]:
        descriptors.extend(
            ResourceDescriptor(
                id=image["id"],
                kind="image",
                source="external" if image.get("href") else "embedded",
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
        series=chart.get("series_count", 0),
        points=sum(series.get("pointCount", 0) for series in chart.get("series", [])),
        title=chart.get("title") or None,
    )
    append_chart_axes(node, chart.get("axes", []))
    if chart.get("unparsed"):
        append(node, "unsupported", type="chart")
    append_plots(node, chart.get("plots", []))
    for series in chart.get("series", []):
        child = append(
            node,
            "series",
            index=series.get("index", 0),
            plot=series.get("plotIndex"),
            axes=" ".join(series.get("axis_ids", [])) or None,
            name=series.get("name") or None,
            hidden=True if series.get("hidden") else None,
        )
        append_annotations(child, series.get("labels", []), series.get("label_options", {}), series.get("trendlines", []))
        append_points(child, series.get("points", []))
    return resource_document("xlsx", node)
