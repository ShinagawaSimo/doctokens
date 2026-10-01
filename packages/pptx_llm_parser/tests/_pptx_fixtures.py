"""Temporary PPTX setup: no real PPTX fixtures exist yet; replace by the atoms in docs/真实测试文件清单.md."""

from __future__ import annotations

import zipfile
from io import BytesIO

from _pptx_namespaces import _PRESENTATION_OVERRIDE as _PRESENTATION_OVERRIDE
from _pptx_namespaces import A_NS as A_NS
from _pptx_namespaces import P14_NS as P14_NS
from _pptx_namespaces import P15_NS as P15_NS
from _pptx_namespaces import P_NS as P_NS
from _pptx_namespaces import PNG_BYTES as PNG_BYTES
from _pptx_namespaces import R_NS as R_NS
from _pptx_objects import chart_shape_xml as chart_shape_xml
from _pptx_objects import chart_xml as chart_xml
from _pptx_objects import diagram_data_xml as diagram_data_xml
from _pptx_objects import diagram_layout_xml as diagram_layout_xml
from _pptx_objects import smartart_shape_xml as smartart_shape_xml
from _pptx_objects import table_shape_xml as table_shape_xml
from _pptx_templates import clr_map_xml as clr_map_xml
from _pptx_templates import layout_xml as layout_xml
from _pptx_templates import master_xml as master_xml
from _pptx_templates import ph_shape_xml as ph_shape_xml
from _pptx_templates import theme_xml as theme_xml


def make_pptx(entries: dict[str, str | bytes]) -> bytes:
    """Pack synthetic ZIP members into bytes for parser unit tests."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def content_types_xml(slide_count: int = 0, *, extra_defaults: str = "") -> str:
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i + 1}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(slide_count)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
{extra_defaults}
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


def presentation_rels_xml(slide_count: int, *, extra: str = "") -> str:
    items = "".join(
        f'<Relationship Id="rId{i + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{i + 1}.xml"/>'
        for i in range(slide_count)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{items}
{extra}
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


def text_shape_xml(
    paragraphs: list[list[tuple[str, str]]],
    *,
    name: str = "TextBox 1",
    shape_id: int = 2,
    geometry: tuple[int, int, int, int] | None = None,
    ph: str | None = None,
) -> str:
    """Build a p:sp with a txBody.

    Each paragraph is a list of segments: ("t", text), ("br", ""), or ("tab", "").
    geometry is (x, y, cx, cy) in EMU; ph is an optional placeholder type.
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
    xfrm = ""
    if geometry:
        x, y, cx, cy = geometry
        xfrm = f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
    nv_pr = f'<p:nvPr><p:ph type="{ph}" idx="0"/></p:nvPr>' if ph else "<p:nvPr/>"
    return f"""<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr/>{nv_pr}</p:nvSpPr>
<p:spPr>{xfrm}</p:spPr>
<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody>
</p:sp>"""


def rich_text_shape_xml(
    paragraphs: list[str],
    *,
    name: str = "Rich 9",
    shape_id: int = 9,
    geometry: tuple[int, int, int, int] | None = None,
) -> str:
    """A p:sp whose paragraphs are raw XML (a:r with rPr, a:br, a:tab...)."""
    body = "".join(f"<a:p>{p}</a:p>" for p in paragraphs)
    xfrm = ""
    if geometry:
        x, y, cx, cy = geometry
        xfrm = f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
    return f"""<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
<p:spPr>{xfrm}</p:spPr>
<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody>
</p:sp>"""


def picture_shape_xml(
    *,
    rid: str = "rId2",
    name: str = "Picture 3",
    alt: str | None = None,
    external: bool = False,
    geometry: tuple[int, int, int, int] | None = None,
) -> str:
    """Build a p:pic with an embedded (r:embed) or external (r:link) blip."""
    blip = f'<a:blip r:link="{rid}"/>' if external else f'<a:blip r:embed="{rid}"/>'
    descr = f' descr="{alt}"' if alt else ""
    xfrm = ""
    if geometry:
        x, y, cx, cy = geometry
        xfrm = f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
    return f"""<p:pic><p:nvPicPr><p:cNvPr id="4" name="{name}"{descr}/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
<p:blipFill>{blip}<a:stretch><a:fillRect/></a:stretch></p:blipFill>
<p:spPr>{xfrm}</p:spPr>
</p:pic>"""


def media_shape_xml(*, rid: str = "rId2", name: str = "Video 4", kind: str = "video") -> str:
    """Build a p14:media shape carrying a video or audio file reference."""
    file_el = f'<p:videoFile r:link="{rid}"/>' if kind == "video" else f'<p:audioFile r:link="{rid}"/>'
    return f"""<p14:media xmlns:p14="{P14_NS}" xmlns:r="{R_NS}" r:embed="{rid}">
<p14:nvPr><p:cNvPr id="5" name="{name}"/><p:cNvPr/><p:nvPr/></p14:nvPr>
<p14:blipFill/>
<p14:stretch/>
<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
<mc:Choice xmlns:p14="{P14_NS}" Requires="p14">{file_el}</mc:Choice>
<mc:Fallback><p:video xmlns:p="{P_NS}" xmlns:r="{R_NS}"/></mc:Fallback>
</mc:AlternateContent>
</p14:media>"""


def slide_rels_xml(rel_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rel_xml}
</Relationships>"""


def comment_authors_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p15:cmAuthorLst xmlns:p15="{P15_NS}">
<p15:cmAuthor id="0" name="Alice" initials="A" lastIndex="2" clrIdx="0"/>
<p15:cmAuthor id="1" name="Bob" initials="B" lastIndex="2" clrIdx="1"/>
</p15:cmAuthorLst>"""


def comments_xml() -> str:
    """Modern threaded comments: one root comment and one reply (parentId)."""
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p15:cmLst xmlns:p15="{P15_NS}" xmlns:a="{a}">
<p15:cm authorId="0" dt="2026-08-13T10:00:00" idx="1">
<p15:pos x="0" y="0"/><p15:text><a:r><a:t>Nice slide</a:t></a:r></p15:text></p15:cm>
<p15:cm authorId="1" dt="2026-08-13T11:00:00" idx="2" parentId="1">
<p15:pos x="0" y="0"/><p15:text><a:r><a:t>Agreed</a:t></a:r></p15:text></p15:cm>
</p15:cmLst>"""


def notes_slide_xml(paragraphs: list[list[tuple[str, str]]]) -> str:
    """Notes slide part: a body placeholder with the given paragraphs."""
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
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notes xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
<p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr/>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder"/><p:cNvSpPr/>
<p:nvPr><p:ph type="body" idx="0"/></p:nvPr></p:nvSpPr>
<p:spPr/>
<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody>
</p:sp>
</p:spTree></p:cSld>
</p:notes>"""


def rich_deck_pptx(*, with_geometry: bool = False) -> bytes:
    """Full-feature two-slide deck: shapes of every type, notes, comments.

    Slide 2 is hidden and carries a bold/red run. with_geometry gives the
    title/body/picture shapes descending coordinates so geometric order
    matches XML order.
    """
    import base64 as _base64

    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    geometry = with_geometry
    title_geo = (0, 685800, 1219200, 342900) if geometry else None
    body_geo = (0, 3429000, 2438400, 685800) if geometry else None
    pic_geo = (0, 5486400, 1219200, 685800) if geometry else None

    slide1 = slide_xml_shapes(
        text_shape_xml([[("t", "Title")]], name="Title 1", ph="title", geometry=title_geo)
        + rich_text_shape_xml(
            [
                "<a:r><a:t>Visit </a:t></a:r>"
                f'<a:r><a:rPr xmlns:a="{a}" xmlns:r="{R_NS}"><a:hlinkClick r:id="rId7"/></a:rPr><a:t>docs</a:t></a:r>'
            ],
            name="Body 2",
            shape_id=3,
            geometry=body_geo,
        )
        + picture_shape_xml(rid="rId2", name="Picture 3", alt="Chart photo", geometry=pic_geo)
        + table_shape_xml([["A", "B"], ["C", "D"]], name="Table 3", shape_id=6)
        + chart_shape_xml(rid="rId3", name="Chart 7", shape_id=7)
        + smartart_shape_xml(dm_rid="rId4", lo_rid="rId5", name="Diagram 8", shape_id=8)
        + media_shape_xml(rid="rId6", name="Video 9")
    )
    secret_run = (
        f'<a:r><a:rPr xmlns:a="{a}"><a:b/><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:rPr><a:t>Secret</a:t></a:r>'
    )
    slide2 = slide_xml_shapes(
        rich_text_shape_xml([secret_run], name="Secret 2", shape_id=2),
        hidden=True,
    )
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(
            2,
            extra_defaults=(
                '<Override PartName="/ppt/charts/chart1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>'
                '<Override PartName="/ppt/diagrams/data1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml"/>'
                '<Override PartName="/ppt/diagrams/layout1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramLayout+xml"/>'
                '<Override PartName="/ppt/notesSlides/notesSlide1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>'
                '<Override PartName="/ppt/comments/comment1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.comments+xml"/>'
                '<Override PartName="/ppt/commentAuthors.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml"/>'
                '<Default Extension="png" ContentType="image/png"/>'
                '<Default Extension="mp4" ContentType="video/mp4"/>'
            ),
        ),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(2),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(
            2,
            extra=(
                '<Relationship Id="rId40" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
                'Target="comments/comment1.xml"/>'
                '<Relationship Id="rId41" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors" '
                'Target="commentAuthors.xml"/>'
            ),
        ),
        "ppt/slides/slide1.xml": slide1,
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="../media/image1.png"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
            'Target="../charts/chart1.xml"/>'
            '<Relationship Id="rId4" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData" '
            'Target="../diagrams/data1.xml"/>'
            '<Relationship Id="rId5" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout" '
            'Target="../diagrams/layout1.xml"/>'
            '<Relationship Id="rId6" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/media" '
            'Target="../media/movie.mp4"/>'
            '<Relationship Id="rId7" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="https://example.test/doc" TargetMode="External"/>'
            '<Relationship Id="rId8" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" '
            'Target="../notesSlides/notesSlide1.xml"/>'
        ),
        "ppt/slides/slide2.xml": slide2,
        "ppt/media/image1.png": _base64.b64decode(PNG_BYTES),
        "ppt/media/movie.mp4": b"",
        "ppt/charts/chart1.xml": chart_xml(),
        "ppt/diagrams/data1.xml": diagram_data_xml(),
        "ppt/diagrams/layout1.xml": diagram_layout_xml(),
        "ppt/notesSlides/notesSlide1.xml": notes_slide_xml([[("t", "Talk")]]),
        "ppt/comments/comment1.xml": comments_xml(),
        "ppt/commentAuthors.xml": comment_authors_xml(),
    }
    return make_pptx(entries)
