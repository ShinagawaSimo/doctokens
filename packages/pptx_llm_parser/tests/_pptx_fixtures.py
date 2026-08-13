"""Programmatic PPTX package fixtures (zero external dependencies)."""

from __future__ import annotations

import zipfile
from io import BytesIO

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def make_pptx(entries: dict[str, str]) -> bytes:
    """Pack a dict of zip member name → XML content into an in-memory PPTX."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


_PRESENTATION_OVERRIDE = (
    '<Override PartName="/ppt/presentation.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
)


def content_types_xml(slide_count: int = 0) -> str:
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i + 1}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(slide_count)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
{_PRESENTATION_OVERRIDE}
{overrides}
</Types>"""


def root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="ppt/presentation.xml"/>\n'
        "</Relationships>"
    )


def presentation_xml(slide_count: int = 0) -> str:
    sld_id_lst = ""
    if slide_count:
        items = "".join(f'<p:sldId id="{256 + i}" r:id="rId{i + 1}"/>' for i in range(slide_count))
        sld_id_lst = f"<p:sldIdLst>{items}</p:sldIdLst>"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}">
{sld_id_lst}
<p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>"""


def presentation_rels_xml(slide_count: int) -> str:
    items = "".join(
        f'<Relationship Id="rId{i + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{i + 1}.xml"/>'
        for i in range(slide_count)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{items}
</Relationships>"""


def slide_xml(*, hidden: bool = False) -> str:
    return slide_xml_shapes("", hidden=hidden)


def slide_xml_shapes(shapes_xml: str, *, hidden: bool = False) -> str:
    show = ' show="0"' if hidden else ""
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}"{show}>
<p:cSld>
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr/>
{shapes_xml}
</p:spTree>
</p:cSld>
</p:sld>"""


def text_shape_xml(paragraphs: list[list[tuple[str, str]]], *, name: str = "TextBox 1", shape_id: int = 2) -> str:
    """Build a p:sp with a txBody.

    Each paragraph is a list of segments: ("t", text), ("br", ""), or ("tab", "").
    """
    body = ""
    for segments in paragraphs:
        runs = ""
        for kind, text in segments:
            if kind == "t":
                runs += f"<a:r><a:t>{text}</a:t></a:r>"
            elif kind == "br":
                runs += "<a:br/>"
            elif kind == "tab":
                runs += "<a:tab/>"
        body += f"<a:p>{runs}</a:p>"
    return f"""<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
<p:spPr/>
<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody>
</p:sp>"""
