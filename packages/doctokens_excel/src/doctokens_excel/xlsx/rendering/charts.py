"""Adapt Excel drawing records to the common bounded chart projection."""

from doctokens_core.ooxml.charts.models import ChartInfo, ChartSeriesInfo

from ..model.drawing import DrawingChart


def preview_info(chart: DrawingChart) -> ChartInfo:
    series: list[ChartSeriesInfo] = []
    for item in chart.get("series", []):
        points = item.get("points", [])
        row: ChartSeriesInfo = {
            "index": item.get("index", len(series)),
            "point_count": item.get("pointCount", len(points)),
        }
        for source, target in (
            ("category", "categories"),
            ("value", "values"),
            ("x", "x_values"),
            ("y", "y_values"),
            ("bubbleSize", "bubble_sizes"),
        ):
            row[target] = [point.get(source, "") for point in points[:8]]  # type: ignore[literal-required]
        for old, new in (
            ("name", "name"),
            ("plotIndex", "plot_index"),
            ("hidden", "hidden"),
            ("axis_ids", "axis_ids"),
            ("labels", "labels"),
            ("label_options", "label_options"),
            ("trendlines", "trendlines"),
        ):
            if old in item:
                row[new] = item[old]  # type: ignore[literal-required]
        series.append(row)
    return {
        "series": series,
        "series_count": chart.get("series_count", len(series)),
        "axes": chart.get("axes", []),
        "plots": chart.get("plots", []),
    }
