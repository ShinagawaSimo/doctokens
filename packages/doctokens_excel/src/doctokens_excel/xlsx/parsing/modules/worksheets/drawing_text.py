"""Read native spreadsheet DrawingML text without inventing layout or field values."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning
from doctokens_core.ooxml.equations.converter import convert_math

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_MATH = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
_A14_M = "{http://schemas.microsoft.com/office/drawing/2010/main}m"


def drawing_paragraphs(body: ET.Element, warnings: list[ParseWarning], part: str) -> list[str]:
    paragraphs: list[str] = []
    for paragraph in body.findall(_A + "p"):
        values: list[str] = []
        for node in paragraph:
            if node.tag in {_A + "r", _A + "fld"}:
                values.append(node.findtext(_A + "t", ""))
            elif node.tag == _A + "br":
                values.append("\n")
            elif node.tag == _A + "tab":
                values.append("\t")
            elif node.tag in {_MATH + "oMath", _MATH + "oMathPara", _A14_M}:
                elements = list(node) if node.tag == _A14_M else [node]
                for math in elements:
                    converted = convert_math(math, warn=lambda c, m: warnings.append(ParseWarning(c, m, part)))
                    values.append(converted.text)
            elif node.tag not in {_A + "pPr", _A + "endParaRPr", _A + "extLst"}:
                values.append("[Unparsed drawing content]")
                warnings.append(ParseWarning("DRAWING_TEXT_UNSUPPORTED", f"Unsupported drawing text child: {node.tag}", part))
        paragraphs.append("".join(values))
    return paragraphs
