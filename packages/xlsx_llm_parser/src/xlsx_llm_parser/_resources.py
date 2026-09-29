"""resources."""

from __future__ import annotations

from html import escape as escape_text

from ooxml_llm_core.models import ResourceDescriptor

from .models import DrawingChart, ParsedWorkbook


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
    attrs = f"id={chart['id']} ref={chart['ref']} type={chart.get('type', '?')}"
    if chart.get("plotTypes"):
        attrs += f" plots={escape_text(','.join(chart['plotTypes']), quote=True)}"
    attrs += f" series={chart.get('series_count', 0)}"
    if chart.get("title"):
        attrs += f" title={escape_text(chart['title'], quote=True)}"
    parts = [f"<chart {attrs}>"]
    is_combination = chart.get("type") == "combination"
    for series in chart.get("series", []):
        series_attrs = f"index={series.get('index', 0)}"
        if series.get("name"):
            series_attrs += f" name={escape_text(series['name'], quote=True)}"
        if "min" in series:
            series_attrs += f" min={series['min']}"
        if "max" in series:
            series_attrs += f" max={series['max']}"
        if is_combination and series.get("chartType"):
            series_attrs += f" type={series['chartType']}"
        if series.get("bubbleSizes"):
            series_attrs += f" bubbleSizes={escape_text(','.join(series['bubbleSizes']), quote=True)}"
        if series.get("hidden"):
            series_attrs += " hidden"
        parts.append(f"\n<series {series_attrs}>")
        for point in series.get("points", []):
            point_attrs = ""
            for name in ("category", "value", "x", "y", "bubbleSize"):
                value = point.get(name, "")
                if value:
                    point_attrs += f" {name}={escape_text(str(value), quote=True)}"
            parts.append(f"\n<point{point_attrs}/>")
    return "".join(parts)
