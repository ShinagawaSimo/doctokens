"""Focused test-only checks for the approved DTX 1.0 vocabulary."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

_ROOT_FORMAT = {"document": "docx", "presentation": "pptx", "workbook": "xlsx"}
_SHARED = {
    "a",
    "b",
    "i",
    "u",
    "color",
    "img",
    "chart",
    "table",
    "tr",
    "td",
    "comments",
    "comment",
    "comment-ref",
}
_TAGS = {
    "docx": _SHARED
    | {
        "body",
        "section",
        "page",
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "th",
        "nested-table",
        "assets",
        "ocr-text",
        "supplemental",
        "footnotes",
        "endnotes",
        "headers",
        "footers",
        "footnote",
        "endnote",
        "header",
        "footer",
        "content-control",
        "mark",
        "s",
        "sup",
        "sub",
        "small-caps",
        "ins",
        "del",
        "cite",
        "br",
        "tab",
        "textbox",
        "equation",
        "smartart",
        "footnote-ref",
        "endnote-ref",
        "field",
        "embedded",
        "unsupported",
    },
    "pptx": _SHARED
    | {
        "slide",
        "title",
        "p",
        "shape",
        "media",
        "smartart",
        "speaker-notes",
        "ocr-text",
        "equation",
    },
    "xlsx": _SHARED
    | {
        "sheet",
        "chart-sheet",
        "defined-names",
        "defined-name",
        "external-links",
        "external-link",
        "columns",
        "sheet-protection",
        "filter",
        "condition",
        "data-validation",
        "pivot-table",
        "table-summary",
        "conditional-format",
        "rule",
        "pivot-cache",
        "slicer",
        "timeline",
        "grid",
        "style-range",
        "cell",
    },
}
_CELL_REF = re.compile(r"[A-Z]+[1-9][0-9]*")
_RANGE_REF = re.compile(r"[A-Z]+[1-9][0-9]*:[A-Z]+[1-9][0-9]*")


def validate_dtx_structure(value: str) -> ET.Element:
    root = ET.fromstring(value)
    format_name = _ROOT_FORMAT.get(root.tag)
    if format_name is None:
        raise ValueError(f"Unapproved DTX root: {root.tag}")
    expected = {"schema": "doctokens-xml", "version": "1.0", "format": format_name}
    if any(root.get(key) != item for key, item in expected.items()):
        raise ValueError("Invalid DTX root metadata")
    if root.get("density") not in {"structural", "semantic"}:
        raise ValueError("Invalid DTX density")
    for parent in root.iter():
        for node in parent:
            if node.tag not in _TAGS[format_name]:
                raise ValueError(f"Unapproved DTX element: {node.tag}")
            if node.tag == "page" and parent.tag not in {"body", "section", "td", "th"}:
                raise ValueError("DOCX page has invalid parent")
            if format_name == "xlsx" and node.tag in {"grid", "tr", "cell"}:
                allowed_parent = {"grid": "sheet", "tr": "grid", "cell": "tr"}[node.tag]
                if parent.tag != allowed_parent:
                    raise ValueError(f"XLSX {node.tag} has invalid parent")
        if parent.tag == "page":
            if format_name != "docx" or list(parent) or (parent.text or "").strip():
                raise ValueError("DOCX page must be an empty milestone")
            if parent.get("number") is None or not parent.get("number", "").isdigit() or int(parent.get("number", "0")) < 1:
                raise ValueError("Invalid DOCX page number")
        if format_name == "xlsx":
            _validate_grid_node(parent)
    return root


def _validate_grid_node(node: ET.Element) -> None:
    if node.tag == "grid" and (node.get("ref") is None or not _RANGE_REF.fullmatch(node.get("ref", ""))):
        raise ValueError("Invalid XLSX grid range")
    if node.tag == "tr" and (
        node.get("number") is None or not node.get("number", "").isdigit() or int(node.get("number", "0")) < 1
    ):
        raise ValueError("Invalid XLSX row number")
    if node.tag == "cell":
        column = node.get("column")
        if column is not None and not re.fullmatch(r"[A-Z]+", column):
            raise ValueError("Invalid XLSX cell column")
        for key in ("formula-range", "spill-range"):
            value = node.get(key)
            if value is not None and not _RANGE_REF.fullmatch(value):
                raise ValueError(f"Invalid XLSX {key}")
        spill_from = node.get("spill-from")
        if spill_from is not None and not _CELL_REF.fullmatch(spill_from):
            raise ValueError("Invalid XLSX spill source")
