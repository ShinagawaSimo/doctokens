"""Adapt Excel drawing records to the common bounded chart projection."""

from doctokens_core.ooxml.charts.models import ChartInfo, ChartPoint, ChartSeriesInfo

from ..model.drawing import DrawingChart


def preview_info(chart: DrawingChart) -> ChartInfo:
    series: list[ChartSeriesInfo] = []
    for item in chart.get("series", []):
        points: list[ChartPoint] = []
        for point in item.get("points", [])[:8]:
            normalized: ChartPoint = {}
            for key, value in point.items():
                normalized["bubble_size" if key == "bubbleSize" else key] = value  # type: ignore[literal-required]
            points.append(normalized)
        row: ChartSeriesInfo = {
            "index": item.get("index", len(series)),
            "points": points,
            "point_count": item.get("pointCount", len(item.get("points", []))),
        }
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
