"""Decode shared strings one SI at a time without retaining the SST XML tree."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.package import PackageReader
from ooxml_llm_core.xml import iterparse

from ....models import RichTextRun

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_SI = f"{{{_NS}}}si"
SharedStrings = list[str] | dict[int, str]


def _parse_shared_strings(
    package_reader: PackageReader, *, include_rich_text: bool, needed_indices: set[int] | None = None
) -> tuple[SharedStrings, dict[int, list[RichTextRun]]]:
    part = "xl/sharedStrings.xml"
    if not package_reader.exists(part):
        return [], {}
    strings: SharedStrings = [] if needed_indices is None else {}
    rich_map: dict[int, list[RichTextRun]] = {}
    root: ET.Element | None = None
    depth = 0
    index = 0
    with package_reader.open_entry(part) as stream:
        for event, element in iterparse(stream, events=("start", "end")):
            if event == "start":
                depth += 1
                if depth == 1:
                    root = element
                continue
            if depth == 2:
                if element.tag == _SI:
                    if needed_indices is None or index in needed_indices:
                        value, rich = _string(element, include_rich_text)
                        if rich is not None:
                            rich_map[index] = rich
                        if isinstance(strings, dict):
                            strings[index] = value
                        else:
                            strings.append(value)
                    index += 1
                element.clear()
                if root is not None:
                    root.remove(element)
            depth -= 1
    return strings, rich_map


def _string(element: ET.Element, rich: bool) -> tuple[str, list[RichTextRun] | None]:
    direct = element.find(f"{{{_NS}}}t")
    if direct is not None:
        return direct.text or "", None
    parts: list[str] = []
    runs: list[RichTextRun] = []
    for run in element.findall(f"{{{_NS}}}r"):
        text = run.find(f"{{{_NS}}}t")
        value = text.text if text is not None and text.text else ""
        parts.append(value)
        properties = run.find(f"{{{_NS}}}rPr") if rich else None
        item: RichTextRun = {"text": value}
        if properties is not None:
            if properties.find(f"{{{_NS}}}b") is not None:
                item["bold"] = True
            if properties.find(f"{{{_NS}}}i") is not None:
                item["italic"] = True
            if properties.find(f"{{{_NS}}}u") is not None:
                item["underline"] = True
            color = properties.find(f"{{{_NS}}}color")
            if color is not None and (rgb := color.get("rgb", "")) and rgb != "00000000":
                item["color"] = f"#{rgb[2:]}" if len(rgb) == 8 else f"#{rgb}"
        runs.append(item)
    return "".join(parts), runs if rich and any(len(run) > 1 for run in runs) else None
