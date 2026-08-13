"""Slide XML parsing: shape text extraction."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ..core.constants import first_child, local_name


class SlideParser:
    """Extract per-slide content from slide part XML."""

    def __init__(self, warnings: list[ParseWarning]) -> None:
        self._warnings = warnings

    def parse_slide(self, root: ET.Element, part: str) -> tuple[bool, list[str]]:
        """Return (hidden, shape_texts) for one p:sld root."""
        if local_name(root.tag) != "sld":
            self._warnings.append(
                ParseWarning(
                    code="SLIDE_INVALID_ROOT",
                    message=f"Slide root element is not p:sld: {root.tag}",
                    locator=part,
                )
            )
        hidden = root.get("show") == "0"
        return hidden, self._shape_texts(root, part)

    def _shape_texts(self, root: ET.Element, part: str) -> list[str]:
        c_sld = first_child(root, "p", "cSld")
        sp_tree = first_child(c_sld, "p", "spTree") if c_sld is not None else None
        if sp_tree is None:
            self._warnings.append(
                ParseWarning(
                    code="SLIDE_MISSING_SPTREE",
                    message="Missing p:cSld/p:spTree",
                    locator=part,
                )
            )
            return []
        texts: list[str] = []
        for child in sp_tree:
            name = local_name(child.tag)
            if name == "sp":
                text = self._shape_text(child, part)
                if text:
                    texts.append(text)
            elif name in {"nvGrpSpPr", "grpSpPr"}:
                continue
            else:
                self._warnings.append(
                    ParseWarning(
                        code="UNSUPPORTED_SHAPE_TYPE",
                        message=f"Unsupported shape type: {name}",
                        locator=part,
                    )
                )
        return texts

    def _shape_text(self, sp: ET.Element, part: str) -> str | None:
        tx_body = first_child(sp, "p", "txBody")
        if tx_body is None:
            return None
        paragraphs: list[str] = []
        for child in tx_body:
            # bodyPr/lstStyle are formatting infrastructure: skipped silently.
            if local_name(child.tag) == "p":
                text = self._paragraph_text(child, part)
                if text:
                    paragraphs.append(text)
        if not paragraphs:
            return None
        return "\n".join(paragraphs)

    def _paragraph_text(self, p: ET.Element, part: str) -> str:
        parts: list[str] = []
        for child in p:
            name = local_name(child.tag)
            if name == "r":
                t = first_child(child, "a", "t")
                if t is not None and t.text:
                    parts.append(t.text)
            elif name == "br":
                parts.append("\n")
            elif name == "tab":
                parts.append("\t")
            elif name == "fld":
                parts.append(self._paragraph_text(child, part))
            elif name in {"pPr", "endParaRPr"}:
                continue
            else:
                self._warnings.append(
                    ParseWarning(
                        code="UNSUPPORTED_PARAGRAPH_CHILD",
                        message=f"Unsupported paragraph child: {name}",
                        locator=part,
                    )
                )
        return "".join(parts)
