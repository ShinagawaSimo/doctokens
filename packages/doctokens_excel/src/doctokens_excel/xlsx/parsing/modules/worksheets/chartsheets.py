"""Validate a chart sheet's explicit drawing binding without scanning it as cell XML."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.models import RelationshipRecord
from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.contracts.models import ParseWarning

from .drawings import DrawingResult, parse_drawings
from .sheet_types import NS_R, NS_S


def parse_chart_sheet(
    package: PackageReader,
    part: str,
    relationships: list[RelationshipRecord],
    *,
    image_start: int,
    chart_start: int,
    shape_start: int,
    warnings: list[ParseWarning],
) -> DrawingResult:
    reason = ""
    try:
        if not package.exists(part):
            reason = "Chart-sheet part is missing"
        else:
            root = package.read_xml(part)
            if root.tag != f"{{{NS_S}}}chartsheet":
                reason = "Chart-sheet root is unsupported"
            else:
                drawing = root.find(f"{{{NS_S}}}drawing")
                rid = drawing.get(f"{{{NS_R}}}id", "") if drawing is not None else ""
                matches = [r for r in relationships if r.id == rid and r.type == f"{NS_R}/drawing"]
                if not matches:
                    reason = "Chart sheet has no resolvable drawing reference"
                else:
                    return parse_drawings(
                        matches,
                        package,
                        image_start=image_start,
                        chart_start=chart_start,
                        shape_start=shape_start,
                        warnings=warnings,
                    )
    except ET.ParseError as exc:
        reason = f"Invalid chart-sheet XML: {exc}"
    warnings.append(ParseWarning("CHART_SHEET_UNREADABLE", reason, part))
    return DrawingResult(
        shapes=[
            {
                "id": f"shape{shape_start}",
                "kind": "unsupported",
                "name": "chart-sheet",
                "unparsed": True,
            }
        ],
        next_shape=shape_start + 1,
    )
