"""Spreadsheet drawing object ownership, saved text and explicit connector references."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.models import RelationshipRecord
from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.contracts.models import ParseWarning
from doctokens_core.ooxml.charts.parser import CHART_RELATIONSHIP_TYPES
from doctokens_core.text.descriptions import first_readable, reading_object_name

from ....model.drawing import DrawingChart, DrawingImage, DrawingShape
from .chart_parts import parse_chart_part
from .drawing_text import drawing_paragraphs
from .post_common import NS_R

XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


class DrawingObjects:
    def __init__(
        self,
        package: PackageReader,
        warnings: list[ParseWarning],
        image_start: int,
        chart_start: int,
        shape_start: int,
    ) -> None:
        self.package, self.warnings = package, warnings
        self.image_start, self.chart_start, self.next_shape = image_start, chart_start, shape_start
        self.images: list[DrawingImage] = []
        self.charts: list[DrawingChart] = []
        self.shapes: list[DrawingShape] = []
        self.identities: dict[str, str] = {}
        self.connectors: list[DrawingShape] = []
        self.addressed: set[str] = set()

    def placeholder(self, ref: str, source: str, group: str = "") -> None:
        item = self._shape_record(ref, "unsupported", group)
        item["name"], item["unparsed"] = source, True
        self.shapes.append(item)

    def _shape_record(self, ref: str, kind: str, group: str) -> DrawingShape:
        item: DrawingShape = {"id": f"shape{self.next_shape}", "ref": ref, "kind": kind}
        self.next_shape += 1
        if group:
            item["group"] = group
        return item

    def visit(self, node: ET.Element, part: str, ref: str, relationships: dict[str, RelationshipRecord], group: str = "") -> None:
        name = node.tag.rsplit("}", 1)[-1]
        if node.tag in {f"{{{XDR}}}{n}" for n in ("nvGrpSpPr", "grpSpPr", "clientData", "from", "to", "pos", "ext")}:
            return
        if node.tag == _MC + "AlternateContent":
            fallback = node.find(_MC + "Fallback")
            if fallback is not None:
                for child in fallback:
                    self.visit(child, part, ref, relationships, group)
            else:
                self.warnings.append(
                    ParseWarning("DRAWING_OBJECT_UNSUPPORTED", "Drawing alternative has no readable fallback", part)
                )
                self.placeholder(ref, "AlternateContent", group)
            return
        if node.tag == f"{{{XDR}}}grpSp":
            item = self._shape_record(ref, "group", group)
            self._metadata(item, node, relationships)
            self.shapes.append(item)
            for child in node:
                self.visit(child, part, ref, relationships, item["id"])
            return
        if node.tag == f"{{{XDR}}}pic":
            self._picture(node, part, ref, relationships, group)
            return
        if node.tag == f"{{{XDR}}}graphicFrame":
            chart = next((child for child in node.iter() if child.tag.rsplit("}", 1)[-1] == "chart"), None)
            relation = relationships.get(chart.get(f"{{{NS_R}}}id", "")) if chart is not None else None
            if relation is not None and relation.type in CHART_RELATIONSHIP_TYPES:
                record = parse_chart_part(self.package, relation.resolved_target or "", self.warnings)
                record.update(
                    {"id": f"chart{self.chart_start + len(self.charts)}", "ref": ref, "part": relation.resolved_target or ""}
                )
                if group:
                    record["group"] = group
                self._identity(node, record["id"])
                self.charts.append(record)
                return
        if node.tag not in {f"{{{XDR}}}sp", f"{{{XDR}}}cxnSp"}:
            self.warnings.append(ParseWarning("DRAWING_OBJECT_UNSUPPORTED", f"Unsupported drawing object: {node.tag}", part))
            self.placeholder(ref, name, group)
            return
        item = self._shape_record(ref, "connector" if name == "cxnSp" else "shape", group)
        self._metadata(item, node, relationships)
        body = node.find(f"{{{XDR}}}txBody")
        if body is not None:
            paragraphs = drawing_paragraphs(body, self.warnings, part)
            item["text"] = "\n".join(paragraphs)
            item["paragraphs"] = paragraphs
            if item["text"]:
                item["kind"] = "textbox" if name != "cxnSp" else "connector"
        if name == "cxnSp":
            for local, key in (("stCxn", "fromShape"), ("endCxn", "toShape")):
                source = next(node.iter(f"{{{A}}}{local}"), None)
                if source is not None and source.get("id"):
                    item[key] = source.get("id", "")  # type: ignore[literal-required]
            self.connectors.append(item)
        self.shapes.append(item)

    def _picture(
        self,
        node: ET.Element,
        part: str,
        ref: str,
        relationships: dict[str, RelationshipRecord],
        group: str,
    ) -> None:
        item: DrawingImage = {"id": f"image{self.image_start + len(self.images)}", "ref": ref}
        properties = next(node.iter(f"{{{XDR}}}cNvPr"), None)
        if properties is not None:
            if description := first_readable(properties.get("descr"), properties.get("title")):
                item["alt"] = description
            hyperlink = properties.find(f"{{{A}}}hlinkClick")
            if hyperlink is not None:
                relation = relationships.get(hyperlink.get(f"{{{NS_R}}}id", ""))
                if relation is not None:
                    item["link"] = relation.target if relation.target_mode == "External" else relation.resolved_target or ""
        if group:
            item["group"] = group
        self._identity(node, item["id"])
        blip = next(node.iter(f"{{{A}}}blip"), None)
        rid = (blip.get(f"{{{NS_R}}}embed") or blip.get(f"{{{NS_R}}}link", "")) if blip is not None else ""
        target = relationships.get(rid or "")
        if target is not None and target.type == f"{NS_R}/image" and target.target_mode == "External":
            item["href"] = target.target
        elif target is not None and target.type == f"{NS_R}/image" and target.resolved_target:
            item["part"] = target.resolved_target
            if not self.package.exists(target.resolved_target):
                item["unparsed"] = True
        else:
            item["unparsed"] = True
        if item.get("unparsed"):
            self.warnings.append(
                ParseWarning("DRAWING_IMAGE_MISSING", "Picture has no readable saved image target", f"{part}#{rid}")
            )
        self.images.append(item)

    def _identity(self, node: ET.Element, identifier: str) -> None:
        properties = next(node.iter(f"{{{XDR}}}cNvPr"), None)
        if properties is not None and properties.get("id"):
            self.identities[properties.get("id", "")] = identifier

    def _metadata(self, item: DrawingShape, node: ET.Element, relationships: dict[str, RelationshipRecord]) -> None:
        properties = next(node.iter(f"{{{XDR}}}cNvPr"), None)
        self._identity(node, item["id"])
        if properties is None:
            return
        for source, key in (("name", "name"), ("descr", "alt"), ("title", "title")):
            value = properties.get(source)
            if source == "name" and item["kind"] == "group":
                value = reading_object_name(value, {"Group"})
            if value:
                item[key] = value  # type: ignore[literal-required]
        hyperlink = properties.find(f"{{{A}}}hlinkClick")
        if hyperlink is not None:
            target = relationships.get(hyperlink.get(f"{{{NS_R}}}id", ""))
            if target is not None:
                item["link"] = target.target if target.target_mode == "External" else target.resolved_target or ""

    def finish_part(self) -> None:
        endpoints = self.addressed
        for item in self.connectors:
            for key in ("fromShape", "toShape"):
                source = item.get(key)
                if isinstance(source, str) and source:
                    target = self.identities.get(source)
                    if target:
                        item[key] = target
                        endpoints.add(target)
                    else:
                        item.pop(key, None)  # type: ignore[misc]
        self.shapes[:] = [
            item
            for item in self.shapes
            if item.get("text")
            or item.get("alt")
            or item.get("title")
            or item.get("link")
            or item["kind"] in {"group", "connector", "unsupported"}
            or item["id"] in endpoints
        ]
        groups = {item["id"]: item for item in self.shapes if item["kind"] == "group"}
        used = {item.get("group", "") for item in (*self.shapes, *self.images, *self.charts) if item.get("kind") != "group"}
        used.update(
            identifier
            for identifier, item in groups.items()
            if item.get("alt") or item.get("title") or item.get("link") or identifier in endpoints
        )
        pending = list(used)
        while pending:
            parent = groups.get(pending.pop(), {}).get("group")
            if parent and parent not in used:
                used.add(parent)
                pending.append(parent)
        self.shapes[:] = [item for item in self.shapes if item["kind"] != "group" or item["id"] in used]
        self.identities.clear()
        self.connectors.clear()
