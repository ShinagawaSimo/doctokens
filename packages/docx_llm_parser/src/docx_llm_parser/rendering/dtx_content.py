"""Dtx content."""

from __future__ import annotations

from collections.abc import Sequence
from xml.etree import ElementTree as ET

from ooxml_llm_core.doctokens_xml import append, text

from ..core.models import (
    ContentControl,
    InlineObject,
    OcrStoredResult,
)
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
    append(parent, "chart", **attrs)


def _append_smartart(parent: ET.Element, smartart: InlineObject) -> None:
    node = append(
        parent,
        "smartart",
        id=smartart.get("id"),
        type=smartart.get("layoutType"),
        nodes=smartart.get("nodeCount", 0),
        links=smartart.get("linkCount", 0),
        truncated=True,
    )
    _append_text_with_breaks(node, " ".join(str(item.get("text", "")) for item in smartart.get("nodes", [])))


def _append_ocr(parent: ET.Element, asset_id: str | None, results: dict[str, OcrStoredResult]) -> None:
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


def _append_controls(parent: ET.Element, controls: Sequence[ContentControl], density: str) -> ET.Element:
    node = parent
    for control in controls:
        attrs: dict[str, object] = {"type": control.get("controlType", "unknown")}
        label = control.get("alias") or control.get("tag")
        if label:
            attrs["label"] = label
        if density == "semantic":
            if control.get("tag") and control.get("tag") != label:
                attrs["tag"] = control["tag"]
            binding = control.get("binding") or {}
            if binding.get("xpath"):
                attrs["binding"] = binding["xpath"]
            attrs.update(
                {
                    key: value
                    for key, value in (
                        ("lock", control.get("lock")),
                        ("placeholder", control.get("placeholder")),
                        ("date_format", control.get("dateFormat")),
                    )
                    if value
                }
            )
            if "checked" in control:
                attrs["checked"] = bool(control["checked"])
        elif control.get("lock") in {"sdtLocked", "contentLocked"}:
            attrs["locked"] = True
        choices = _control_choices(control)
        if choices:
            attrs["choices"] = choices
        node = append(node, "content-control", **attrs)
    return node


def _control_choices(control: ContentControl) -> str:
    choices: list[str] = []
    for option in control.get("options", []):
        display = str(option.get("display") or "")
        value = str(option.get("value") or "")
        choices.append(f"{display}={value}" if display and value and display != value else display or value)
    return "|".join(item for item in choices if item)


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
