"""Read worksheet and chart-sheet drawing relationships, preserving visible failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.models import RelationshipRecord
from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.contracts.models import ParseWarning

from ....model.coordinates import col_letter
from ....model.drawing import DrawingChart, DrawingImage, DrawingShape
from .drawing_objects import XDR, DrawingObjects
from .post_common import NS_R

_REL_DRAWING = f"{NS_R}/drawing"


@dataclass(slots=True)
class DrawingResult:
    images: list[DrawingImage] = field(default_factory=list)
    charts: list[DrawingChart] = field(default_factory=list)
    shapes: list[DrawingShape] = field(default_factory=list)
    next_shape: int = 1


def parse_drawings(
    sheet_rels: list[RelationshipRecord],
    pkg: PackageReader,
    *,
    image_start: int = 1,
    chart_start: int = 1,
    shape_start: int = 1,
    warnings: list[ParseWarning],
) -> DrawingResult:
    objects = DrawingObjects(pkg, warnings, image_start, chart_start, shape_start)
    seen: set[str] = set()
    for relationship in sheet_rels:
        if relationship.type != _REL_DRAWING:
            continue
        part = relationship.resolved_target
        if part in seen:
            continue
        if part is None or not pkg.exists(part):
            warnings.append(
                ParseWarning(
                    "DRAWING_PART_MISSING", "Referenced drawing part is missing", f"{relationship.source_part}#{relationship.id}"
                )
            )
            objects.placeholder("", "drawing")
            continue
        seen.add(part)
        try:
            root = pkg.read_xml(part)
        except ET.ParseError as exc:
            warnings.append(ParseWarning("DRAWING_XML_INVALID", f"Invalid drawing XML: {exc}", part))
            objects.placeholder("", "drawing")
            continue
        if root.tag != f"{{{XDR}}}wsDr":
            warnings.append(ParseWarning("DRAWING_ROOT_UNSUPPORTED", f"Unsupported drawing root: {root.tag}", part))
            objects.placeholder("", "drawing")
            continue
        relationships: dict[str, RelationshipRecord] = {}
        try:
            relationships = {r.id: r for r in pkg.read_relationships_for_part(part)}
        except (ET.ParseError, ValueError, KeyError) as exc:
            warnings.append(ParseWarning("DRAWING_RELS_XML_INVALID", f"Invalid drawing relationships: {exc}", part))
        for anchor in root:
            if anchor.tag not in {f"{{{XDR}}}{name}" for name in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor")}:
                if anchor.tag != f"{{{XDR}}}extLst":
                    objects.placeholder("", anchor.tag.rsplit("}", 1)[-1])
                continue
            ref = _anchor_ref(anchor, warnings, part)
            counts = len(objects.images), len(objects.charts), len(objects.shapes)
            for node in anchor:
                objects.visit(node, part, ref, relationships)
            end = _anchor_ref(anchor, warnings, part, marker="to") if anchor.tag == f"{{{XDR}}}twoCellAnchor" else ""
            if ref and end:
                for item in [*objects.images[counts[0] :], *objects.charts[counts[1] :], *objects.shapes[counts[2] :]]:
                    item["anchorRange"] = f"{ref}:{end}"
        objects.finish_part()
    return DrawingResult(objects.images, objects.charts, objects.shapes, objects.next_shape)


def _anchor_ref(anchor: ET.Element, warnings: list[ParseWarning], part: str, *, marker: str = "from") -> str:
    start = anchor.find(f"{{{XDR}}}{marker}")
    if start is None:
        return ""
    try:
        column = int(start.findtext(f"{{{XDR}}}col", ""))
        row = int(start.findtext(f"{{{XDR}}}row", ""))
        if not (0 <= column < 16384 and 0 <= row < 1048576):
            raise ValueError("outside worksheet bounds")
    except ValueError:
        warnings.append(ParseWarning("DRAWING_ANCHOR_INVALID", "Drawing anchor has invalid row/column coordinates", part))
        return ""
    return f"{col_letter(column + 1)}{row + 1}"
