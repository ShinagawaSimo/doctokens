"""Select saved historical properties and describe changes in reading semantics."""

from __future__ import annotations

from collections.abc import Mapping
from xml.etree import ElementTree as ET

from ..model import StyleRecord
from ..model.content import PropertyChange, ReviewMarkup, Revision
from .formatting import merge_paragraph_borders, parse_paragraph_alignment, parse_paragraph_borders
from .namespaces import attr, first_child, is_on, local_name
from .numbering import NumberingMap
from .styles import StyleMap


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


def reading_properties(
    properties: ET.Element | None,
    *,
    styles: StyleMap,
    numbering: NumberingMap | None = None,
    table_style: StyleRecord | None = None,
) -> dict[str, object]:
    """Resolve supported reading properties; never fall back to source IDs/settings."""
    result: dict[str, object] = {}
    if properties is None:
        return result
    scope = local_name(properties.tag)
    if scope == "pPr":
        style_id = attr(first_child(properties, "w", "pStyle"), "w", "val")
        inherited = styles.paragraph(style_id, table_style)
        alignment = parse_paragraph_alignment(properties) or inherited.alignment
        if alignment and alignment != "left":
            result["align"] = alignment
        outline = _integer(properties, "outlineLvl", inherited.outline_level)
        if outline is not None and 0 <= outline < 9:
            result["outline"] = outline
        borders = merge_paragraph_borders(inherited.borders, parse_paragraph_borders(properties, styles.theme))
        for side, border in borders.items():
            if border["style"] not in {"nil", "none"}:
                result[f"border-{side}"] = border["style"] + (f":{border['color']}" if border.get("color") else "")
        num_pr = first_child(properties, "w", "numPr")
        num_id = attr(first_child(num_pr, "w", "numId"), "w", "val") or inherited.numbering_num_id
        if numbering is not None and num_id and num_id != "0":
            level = _integer(num_pr, "ilvl", None)
            if level is None:
                level = numbering.level_for_style(num_id, style_id or "")
            if level is None:
                level = inherited.numbering_level or 0
            if level is not None and (definition := numbering.level_for(num_id, level)) is not None:
                result["numbering"] = definition.number_format
                result["level"] = level
    elif scope == "tblPr":
        style_id = attr(first_child(properties, "w", "tblStyle"), "w", "val")
        background = styles.table(style_id, []).cell_background
        shading = first_child(properties, "w", "shd")
        if shading is not None:
            background = styles.theme.color(shading, fill=True) if attr(shading, "w", "val") != "nil" else None
        if background:
            result["background"] = background
    elif scope == "trPr":
        for source, target in (("gridBefore", "grid-before"), ("gridAfter", "grid-after")):
            if (value := _integer(properties, source, 0)) is not None and value > 0:
                result[target] = value
        if is_on(first_child(properties, "w", "tblHeader")):
            result["header"] = True
    elif scope == "tcPr":
        span = _integer(properties, "gridSpan", 1)
        if span is not None and span > 1:
            result["colspan"] = span
        merge = first_child(properties, "w", "vMerge")
        if merge is not None:
            result["v-merge"] = "restart" if attr(merge, "w", "val") == "restart" else "continue"
        shading = first_child(properties, "w", "shd")
        background = table_style.cell_background if table_style is not None else None
        if shading is not None:
            background = styles.theme.color(shading, fill=True) if attr(shading, "w", "val") != "nil" else None
        if background:
            result["background"] = background
    return result


def _integer(properties: ET.Element | None, name: str, default: int | None) -> int | None:
    value = attr(first_child(properties, "w", name), "w", "val")
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def apply_property_review(
    markup: ReviewMarkup,
    properties: ET.Element | None,
    scope: str,
    view: str,
    *,
    styles: StyleMap,
    numbering: NumberingMap | None = None,
    table_style: StyleRecord | None = None,
) -> None:
    if view != "review":
        return
    revision = structural_revision(properties)
    if revision is not None:
        markup["revisions"] = [revision_record(revision)]
    change = property_change(
        properties,
        scope,
        reading_properties(
            selected_properties(properties, "original"), styles=styles, numbering=numbering, table_style=table_style
        ),
        reading_properties(properties, styles=styles, numbering=numbering, table_style=table_style),
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
