"""Minimal test projections for cross-entry DTX semantics."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning


def extract_text_events(value: str, format_name: str) -> list[tuple[str, str]]:
    root = ET.fromstring(value)
    if format_name == "docx":
        return [
            (node.tag, "".join(node.itertext()))
            for node in root.findall(".//body/*")
            if node.tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
        ]
    if format_name == "pptx":
        return [
            (slide.get("number", ""), "".join(node.itertext()))
            for slide in root.findall("slide")
            for node in slide
            if node.tag in {"p", "title"}
        ]
    if format_name == "xlsx":
        return [
            (sheet.get("name", ""), "".join(cell.itertext()))
            for sheet in root.findall("sheet")
            for cell in sheet.findall(".//grid/tr/cell")
        ]
    raise ValueError(format_name)


def extract_page_events(value: str) -> list[int]:
    return [int(node.attrib["number"]) for node in ET.fromstring(value).findall(".//page")]


def extract_reference_events(value: str) -> list[tuple[str, str]]:
    return [
        (node.tag, node.get("href") or node.get("id") or "")
        for node in ET.fromstring(value).iter()
        if node.tag in {"a", "footnote-ref", "endnote-ref", "comment-ref"}
    ]


def extract_object_events(value: str) -> list[tuple[str, str, str]]:
    return [
        (node.tag, node.get("id", ""), node.get("truncated", "false"))
        for node in ET.fromstring(value).iter()
        if node.tag in {"img", "chart", "smartart", "media", "table", "table-summary"}
    ]


def extract_warning_events(warnings: list[ParseWarning]) -> list[tuple[str, str | None]]:
    return [(warning.code, warning.locator) for warning in warnings]
