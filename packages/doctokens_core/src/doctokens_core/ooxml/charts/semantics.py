"""Read saved chart annotations and explicit plot/axis relationships without calculation."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .models import ChartLabel

_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
_CX = "{http://schemas.microsoft.com/office/drawing/2014/chartex}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_C15 = "{http://schemas.microsoft.com/office/drawing/2012/chart}"
_LABEL_FLAGS = ("showLegendKey", "showVal", "showCatName", "showSerName", "showPercent", "showBubbleSize")


def saved_text(node: ET.Element | None, namespace: str = _C) -> str:
    if node is None:
        return ""
    rich = node.find(namespace + "rich")
    if rich is None:
        rich = node.find(namespace + "tx/" + namespace + "rich")
    if rich is not None:
        paragraphs = []
        for paragraph in rich.findall(_A + "p"):
            values = []
            for child in paragraph:
                if child.tag in {_A + "r", _A + "fld"}:
                    values.append(child.findtext(_A + "t", ""))
                elif child.tag == _A + "br":
                    values.append("\n")
                elif child.tag == _A + "tab":
                    values.append("\t")
            paragraphs.append("".join(values))
        return "\n".join(paragraphs)
    texts = node.findall(namespace + "strRef/" + namespace + "strCache/" + namespace + "pt/" + namespace + "v")
    if not texts:
        texts = node.findall(namespace + "txData/" + namespace + "v")
    if not texts:
        texts = node.findall(namespace + "v")
    return "\n".join(value.text or "" for value in texts)


def label_options(container: ET.Element, prefix: str = _C) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in _LABEL_FLAGS:
        node = container.find(prefix + name)
        if node is not None:
            result[name] = node.get("val", "1")
    separator = container.find(prefix + "separator")
    if separator is not None:
        result["separator"] = separator.text or ""
    visibility = container.find(_CX + "visibility")
    if visibility is not None:
        result.update(visibility.attrib)
    show_range = container.find(_C + "extLst/" + _C + "ext/" + _C15 + "showDataLabelsRange")
    if show_range is not None:
        result["showDataLabelsRange"] = show_range.get("val", "1")
    return result


def series_labels(series: ET.Element, *, chartex: bool = False) -> tuple[list[ChartLabel], dict[str, str]]:
    prefix = _CX if chartex else _C
    container = series.find(prefix + ("dataLabels" if chartex else "dLbls"))
    if container is None:
        container = ET.Element(prefix + "dataLabels")
    labels: list[ChartLabel] = []
    for source in container:
        if source.tag not in {prefix + ("dataLabel" if chartex else "dLbl"), _CX + "dataLabelHidden"}:
            continue
        label: ChartLabel = {}
        raw_index = source.get("idx") if chartex else source.findtext(_C + "idx")
        if not chartex:
            index = source.find(_C + "idx")
            raw_index = index.get("val") if index is not None else None
        try:
            if raw_index is not None and int(raw_index) >= 0:
                label["index"] = int(raw_index)
        except ValueError:
            pass
        tx = source.find(prefix + "tx")
        value = saved_text(tx, prefix)
        if value:
            label["text"] = value
        elif (
            tx is not None
            and tx.find(prefix + "strRef") is not None
            and tx.find(prefix + "strRef/" + prefix + "strCache") is None
        ):
            label["unsupported"] = True
        position = source.get("pos") if chartex else None
        if not chartex and (node := source.find(_C + "dLblPos")) is not None:
            position = node.get("val")
        if position:
            label["position"] = position
        deleted = source.find(_C + "delete")
        if source.tag == _CX + "dataLabelHidden" or (deleted is not None and deleted.get("val", "1") in {"1", "true"}):
            label["deleted"] = True
        if options := label_options(source, prefix):
            label["options"] = options
        labels.append(label)
    if not chartex:
        selected = {label["index"]: label for label in labels if "index" in label}
        for cache in series.findall(_C + "extLst/" + _C + "ext/" + _C15 + "datalabelsRange/" + _C15 + "dlblRangeCache"):
            for point in cache.findall(_C + "pt"):
                try:
                    point_index = int(point.get("idx", ""))
                except ValueError:
                    continue
                if point_index < 0:
                    continue
                label_text = point.findtext(_C + "v")
                if label_text is None:
                    continue
                cached_label = selected.get(point_index)
                if cached_label is None:
                    cached_label = {"index": point_index, "text": label_text}
                    labels.append(cached_label)
                    selected[point_index] = cached_label
                elif not cached_label.get("text") and not cached_label.get("deleted"):
                    cached_label["text"] = label_text
    return labels, label_options(container, prefix)


def trendlines(series: ET.Element) -> list[dict[str, str]]:
    result = []
    for source in series.findall(_C + "trendline"):
        item: dict[str, str] = {}
        for field, name in (
            ("type", "trendlineType"),
            ("order", "order"),
            ("period", "period"),
            ("forward", "forward"),
            ("backward", "backward"),
            ("intercept", "intercept"),
            ("display-equation", "dispEq"),
            ("display-r-squared", "dispRSqr"),
        ):
            child = source.find(_C + name)
            if child is not None:
                item[field] = child.get("val", "1" if name.startswith("disp") else "")
        if title := source.findtext(_C + "name"):
            item["name"] = title
        label = source.find(_C + "trendlineLbl/" + _C + "tx")
        if label is not None and (value := saved_text(label)):
            item["label"] = value
        result.append(item)
    return result


def axis_ids(node: ET.Element, *, chartex: bool = False) -> list[str]:
    prefix, name = (_CX, "axisId") if chartex else (_C, "axId")
    return [item.get("val") or item.text or "" for item in node.findall(prefix + name) if item.get("val") or item.text]
