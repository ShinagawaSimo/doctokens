"""解析 DOCX 中被 DrawingML 引用的图表和 SmartArt。"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from ..core.constants import attr, first_child, local_name, qn
from ..core.models import ParseWarning
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex

CHART_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
DIAGRAM_DATA_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData"
)

CHART_TYPE_MAP = {
    "areaChart": "area",
    "area3DChart": "area3d",
    "barChart": "bar",
    "bar3DChart": "bar3d",
    "bubbleChart": "bubble",
    "doughnutChart": "doughnut",
    "lineChart": "line",
    "line3DChart": "line3d",
    "ofPieChart": "ofPie",
    "pieChart": "pie",
    "pie3DChart": "pie3d",
    "radarChart": "radar",
    "scatterChart": "scatter",
    "surfaceChart": "surface",
    "surface3DChart": "surface3d",
}

MAX_PREVIEW_POINTS = 8


class EmbeddedObjectExtractor:
    """从 chart/diagram relationships 中构建轻量对象索引。"""

    def __init__(
        self,
        package: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
    ) -> None:
        self.package = package
        self.relationships = relationships
        self.warnings = warnings

    def extract(self) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict], list[dict]]:
        """解析图表和 SmartArt，并返回 `(sourcePart, rId)` 索引。"""
        lookup: dict[tuple[str, str], dict[str, Any]] = {}
        charts = self._extract_charts(lookup)
        smartarts = self._extract_smartarts(lookup)
        return lookup, charts, smartarts

    def _extract_charts(self, lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict]:
        """解析 chart relationships 指向的图表 part。"""
        charts: list[dict] = []
        for chart_index, rel in enumerate(self.relationships.by_type(CHART_REL_TYPE), start=1):
            chart_id = f"chart{chart_index}"
            target = rel.resolved_target
            if rel.target_mode == "External" or not target or not self.package.exists(target):
                # 图表 part 缺失时保留 warning，正文里会降级成轻量占位。
                self._warn(
                    "CHART_TARGET_MISSING",
                    f"Chart target is missing: {target}",
                    part=rel.source_part,
                )
                continue
            try:
                with self.package.open_entry(target) as stream:
                    root = ET.parse(stream).getroot()
                chart = parse_chart_root(root, chart_id, target)
            except Exception as exc:
                self._warn(
                    "CHART_PARSE_FAILED",
                    f"Failed to parse chart part {target}: {exc}",
                    part=target,
                )
                continue
            chart["sourcePart"] = rel.source_part
            chart["relationshipId"] = rel.id
            charts.append(chart)
            lookup[(rel.source_part, rel.id)] = chart
        return charts

    def _extract_smartarts(self, lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict]:
        """解析 SmartArt data model relationships 指向的 diagram data part。"""
        smartarts: list[dict] = []
        for item_index, rel in enumerate(
            self.relationships.by_type(DIAGRAM_DATA_REL_TYPE), start=1
        ):
            smartart_id = f"smartart{item_index}"
            target = rel.resolved_target
            if rel.target_mode == "External" or not target or not self.package.exists(target):
                # data model 缺失时正文仍可输出 SmartArt 占位。
                self._warn(
                    "SMARTART_TARGET_MISSING",
                    f"SmartArt data target is missing: {target}",
                    part=rel.source_part,
                )
                continue
            try:
                with self.package.open_entry(target) as stream:
                    root = ET.parse(stream).getroot()
                smartart = parse_smartart_root(root, smartart_id, target)
            except Exception as exc:
                self._warn(
                    "SMARTART_PARSE_FAILED",
                    f"Failed to parse SmartArt data part {target}: {exc}",
                    part=target,
                )
                continue
            smartart["sourcePart"] = rel.source_part
            smartart["relationshipId"] = rel.id
            smartarts.append(smartart)
            lookup[(rel.source_part, rel.id)] = smartart
        return smartarts

    def _warn(self, code: str, message: str, part: str | None = None) -> None:
        """记录对象解析 warning。"""
        self.warnings.append(ParseWarning(level="warning", code=code, message=message, part=part))


def parse_chart_root(root: ET.Element, chart_id: str, part_name: str) -> dict[str, Any]:
    """从 chart XML 中抽取 LLM 需要的轻量图表信息。"""
    plot_area = root.find(".//" + qn("c", "plotArea"))
    chart_type = _chart_type(plot_area)
    series = _chart_series(plot_area)
    point_count = sum(item["pointCount"] for item in series)
    chart: dict[str, Any] = {
        "id": chart_id,
        "type": "chart",
        "chartType": chart_type,
        "part": part_name,
        "seriesCount": len(series),
        "pointCount": point_count,
        "series": series,
    }
    title = _chart_title(root)
    if title:
        chart["title"] = title
    return chart


def parse_smartart_root(root: ET.Element, smartart_id: str, part_name: str) -> dict[str, Any]:
    """从 SmartArt data model 中抽取节点文字和连接关系。"""
    nodes: list[dict[str, Any]] = []
    node_index_by_model_id: dict[str, int] = {}
    for point in root.iter(qn("dgm", "pt")):
        model_id = point.attrib["modelId"]
        text = _drawing_text(point)
        if not text:
            continue
        node = {"modelId": model_id, "text": text}
        point_type = point.get("type")
        if point_type:
            node["kind"] = point_type
        node_index_by_model_id[model_id] = len(nodes) + 1
        nodes.append(node)

    links: list[dict[str, Any]] = []
    raw_link_count = 0
    for connection in root.iter(qn("dgm", "cxn")):
        raw_link_count += 1
        source = connection.get("srcId")
        target = connection.get("destId")
        if source in node_index_by_model_id and target in node_index_by_model_id:
            # 最终 XML 使用短序号引用节点，避免暴露冗长 modelId。
            link: dict[str, Any] = {
                "from": node_index_by_model_id[source],
                "to": node_index_by_model_id[target],
            }
            kind = connection.get("type")
            if kind:
                link["kind"] = kind
            links.append(link)

    return {
        "id": smartart_id,
        "type": "smartart",
        "part": part_name,
        "nodeCount": len(nodes),
        "linkCount": len(links),
        "rawLinkCount": raw_link_count,
        "nodes": nodes,
        "links": links,
    }


def _chart_type(plot_area: ET.Element | None) -> str | None:
    """识别 plotArea 下第一个图表类型。"""
    if plot_area is None:
        return None
    for item in plot_area:
        lname = local_name(item.tag)
        if lname in CHART_TYPE_MAP:
            return CHART_TYPE_MAP[lname]
    return None


def _chart_title(root: ET.Element) -> str | None:
    """读取图表标题富文本。"""
    title = root.find(".//" + qn("c", "title"))
    if title is None:
        return None
    return _drawing_text(title) or None


def _chart_series(plot_area: ET.Element | None) -> list[dict[str, Any]]:
    """解析所有 c:ser，并生成轻量数据摘要。"""
    if plot_area is None:
        return []
    rows: list[dict[str, Any]] = []
    for ser_index, ser in enumerate(plot_area.iter(qn("c", "ser")), start=1):
        categories = _cached_values(first_child(ser, "c", "cat")) or _cached_values(
            first_child(ser, "c", "xVal")
        )
        values = _cached_values(first_child(ser, "c", "val")) or _cached_values(
            first_child(ser, "c", "yVal")
        )
        name = _series_name(ser)
        point_count = max(len(categories), len(values))
        row: dict[str, Any] = {
            "index": ser_index,
            "pointCount": point_count,
            "preview": _series_preview(categories, values),
        }
        if name:
            row["name"] = name
        value_numbers = [_to_float(value) for value in values]
        value_numbers = [value for value in value_numbers if value is not None]
        if value_numbers:
            # min/max 支持用户快速理解趋势和范围。
            row["min"] = min(value_numbers)
            row["max"] = max(value_numbers)
        formula = _first_formula(ser)
        if formula:
            row["formula"] = formula
        rows.append(row)
    return rows


def _series_name(ser: ET.Element) -> str | None:
    """读取系列名，优先使用缓存字符串。"""
    tx = first_child(ser, "c", "tx")
    if tx is None:
        return None
    values = _cached_values(tx)
    if values:
        return values[0]
    return _first_chart_value(tx)


def _cached_values(node: ET.Element | None) -> list[str]:
    """读取 strCache/numCache 中按点保存的值。"""
    if node is None:
        return []
    points: list[tuple[int, str]] = []
    for point in node.iter(qn("c", "pt")):
        value = first_child(point, "c", "v")
        if value is None:
            continue
        idx = int(point.get("idx") or len(points))
        points.append((idx, value.text or ""))
    return [value for _idx, value in sorted(points, key=lambda item: item[0])]


def _first_chart_value(node: ET.Element) -> str | None:
    """读取 chart 子树中的第一个 c:v 文本。"""
    value = node.find(".//" + qn("c", "v"))
    if value is None:
        return None
    return value.text or None


def _first_formula(node: ET.Element) -> str | None:
    """读取系列数据来源公式，仅进入 debug/内部对象。"""
    formula = node.find(".//" + qn("c", "f"))
    if formula is None:
        return None
    return formula.text or None


def _series_preview(categories: list[str], values: list[str]) -> str:
    """生成少量点预览，避免把大图表全量塞进段落 XML。"""
    items: list[str] = []
    count = max(len(categories), len(values))
    for index in range(min(count, MAX_PREVIEW_POINTS)):
        category = categories[index] if index < len(categories) else str(index + 1)
        value = values[index] if index < len(values) else ""
        items.append(f"{category}={value}" if value else category)
    return "; ".join(items)


def _drawing_text(node: ET.Element) -> str:
    """读取 DrawingML/diagram 富文本中的 a:t 文本。"""
    parts: list[str] = []
    for item in node.iter():
        if item.tag == qn("a", "t"):
            parts.append(item.text or "")
    return "".join(parts).strip()


def _to_float(value: str) -> float | None:
    """把 chart cache 中的数值文本转为 float。"""
    try:
        return float(value)
    except ValueError:
        return None
