"""Select saved historical properties and describe changes in reading semantics."""

from __future__ import annotations

from collections.abc import Mapping
from xml.etree import ElementTree as ET

from ..model.content import PropertyChange, ReviewMarkup, Revision
from .namespaces import attr, first_child, local_name
from .table_styles import table_look


def properties_change(properties: ET.Element | None) -> ET.Element | None:
    if properties is None:
        return None
    return first_child(properties, "w", local_name(properties.tag) + "Change")


def selected_properties(properties: ET.Element | None, view: str) -> ET.Element | None:
    if properties is not None and view == "original":
        previous = first_child(properties_change(properties), "w", local_name(properties.tag))
        if previous is not None:
            return previous
    return properties


def describe_properties(values: Mapping[str, object]) -> str:
    return (
        ";".join(f"{key}={str(value).lower() if isinstance(value, bool) else value}" for key, value in sorted(values.items()))
        or "normal"
    )


def property_change(
    properties: ET.Element | None, scope: str, before: Mapping[str, object], after: Mapping[str, object]
) -> PropertyChange | None:
    change = properties_change(properties)
    if change is None or before == after:
        return None
    return {
        "scope": scope,
        "before": describe_properties(before),
        "after": describe_properties(after),
        "author": attr(change, "w", "author") or "",
        "date": attr(change, "w", "date") or "",
    }


def revision_record(node: ET.Element, kind: str | None = None) -> Revision:
    source = kind or local_name(node.tag)
    record: Revision = {
        "kind": "deleted" if source in {"del", "cellDel", "moveFrom"} else "inserted",
        "author": attr(node, "w", "author") or "",
        "date": attr(node, "w", "date") or "",
        "moveName": "",
    }
    if source in {"moveFrom", "moveTo"}:
        record["kind"] = "moved-from" if source == "moveFrom" else "moved-to"
    return record


def retained_revision(node: ET.Element | None, view: str) -> bool:
    if node is None or view == "review":
        return True
    deleted = local_name(node.tag) in {"del", "cellDel", "moveFrom"}
    return (view == "original") == deleted


def structural_revision(properties: ET.Element | None) -> ET.Element | None:
    if properties is not None:
        for child in properties:
            if local_name(child.tag) in {"ins", "del", "moveFrom", "moveTo", "cellIns", "cellDel"}:
                return child
    return None


def reading_properties(properties: ET.Element | None) -> dict[str, object]:
    """Summarize only properties used by the reading model, excluding layout."""
    result: dict[str, object] = {}
    names = {
        "pStyle": "style",
        "tblStyle": "style",
        "jc": "align",
        "outlineLvl": "outline",
        "gridBefore": "grid-before",
        "gridAfter": "grid-after",
        "gridSpan": "colspan",
        "vMerge": "v-merge",
        "tblHeader": "header",
        "tblLook": "regions",
        "tblStyleRowBandSize": "row-band",
        "tblStyleColBandSize": "column-band",
    }
    if properties is not None:
        for node in properties:
            name = local_name(node.tag)
            if name == "tblLook":
                result["regions"] = ",".join(key for key, enabled in table_look(node).items() if enabled) or "banded"
            elif name in names:
                result[names[name]] = attr(node, "w", "val") or "true"
            elif name == "shd":
                result["background"] = attr(node, "w", "fill") or "auto"
            elif name == "numPr":
                result["numbering"] = attr(first_child(node, "w", "numId"), "w", "val") or "0"
                result["level"] = attr(first_child(node, "w", "ilvl"), "w", "val") or "0"
            elif name == "pBdr":
                result["borders"] = ",".join(
                    f"{local_name(side.tag)}:{attr(side, 'w', 'val')}:{attr(side, 'w', 'color') or ''}" for side in node
                )
    return result


def apply_property_review(markup: ReviewMarkup, properties: ET.Element | None, scope: str, view: str) -> None:
    if view != "review":
        return
    revision = structural_revision(properties)
    if revision is not None:
        markup["revisions"] = [revision_record(revision)]
    change = property_change(
        properties, scope, reading_properties(selected_properties(properties, "original")), reading_properties(properties)
    )
    if change:
        markup.setdefault("propertyChanges", []).append(change)
    merge = first_child(properties, "w", "cellMerge")
    if merge is not None and attr(merge, "w", "vMergeOrig") != attr(merge, "w", "vMerge"):
        labels = {"cont": "continue", "rest": "restart"}
        before = attr(merge, "w", "vMergeOrig") or "none"
        after = attr(merge, "w", "vMerge") or "none"
        markup.setdefault("propertyChanges", []).append(
            {
                "scope": "cell",
                "before": "v-merge=" + labels.get(before, before),
                "after": "v-merge=" + labels.get(after, after),
                "author": attr(merge, "w", "author") or "",
                "date": attr(merge, "w", "date") or "",
            }
        )
