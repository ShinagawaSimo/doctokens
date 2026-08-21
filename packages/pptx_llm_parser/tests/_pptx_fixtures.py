"""Programmatic PPTX package fixtures (zero external dependencies)."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

from test_support.file_contract import materialize_bytes

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"

# 1x1 transparent PNG (base64).
PNG_BYTES = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def make_pptx(entries: dict[str, str | bytes]) -> Path:
    """Pack a dict of ZIP members into a real PPTX input file."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return materialize_bytes(buffer.getvalue(), suffix=".pptx", package="pptx", name="generated")


_PRESENTATION_OVERRIDE = (
    '<Override PartName="/ppt/presentation.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
)


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


def theme_xml() -> str:
    """Theme part with a clrScheme: srgb values plus one sysClr slot."""
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{a}" name="Test Theme">
<a:themeElements>
<a:clrScheme name="Test">
<a:dk1><a:sysClr val="windowText" lastClr="1A1A1A"/></a:dk1>
<a:lt1><a:sysClr val="window" lastClr="FEFEFE"/></a:lt1>
<a:dk2><a:srgbClr val="44546A"/></a:dk2>
<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>
<a:accent1><a:srgbClr val="4472C4"/></a:accent1>
<a:accent2><a:srgbClr val="ED7D31"/></a:accent2>
<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>
<a:accent4><a:srgbClr val="FFC000"/></a:accent4>
<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>
<a:accent6><a:srgbClr val="70AD47"/></a:accent6>
<a:hlink><a:srgbClr val="0563C1"/></a:hlink>
<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
</a:clrScheme>
</a:themeElements>
</a:theme>"""


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


P15_NS = "http://schemas.microsoft.com/office/powerpoint/2012/main"


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


def ph_shape_xml(*, idx: str, ph_type: str, geometry: tuple[int, int, int, int] | None = None, shape_id: int = 2) -> str:
    """A placeholder p:sp (as found in layouts/masters), optionally with geometry."""
    xfrm = ""
    if geometry:
        x, y, cx, cy = geometry
        xfrm = f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
    return f"""<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="PH {idx}"/><p:cNvSpPr/>
<p:nvPr><p:ph type="{ph_type}" idx="{idx}"/></p:nvPr></p:nvSpPr>
<p:spPr>{xfrm}</p:spPr>
<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>
</p:sp>"""


def clr_map_xml(**mapping: str) -> str:
    attrs = " ".join(f'{name}="{value}"' for name, value in mapping.items())
    return f"<p:clrMap {attrs}/>"


def layout_xml(shapes_xml: str = "", *, clr_map: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
<p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/>{shapes_xml}</p:spTree></p:cSld>
{clr_map}
</p:sldLayout>"""


def master_xml(shapes_xml: str = "", *, clr_map: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
<p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/>{shapes_xml}</p:spTree></p:cSld>
{clr_map}
</p:sldMaster>"""


def chart_shape_xml(*, rid: str = "rId2", name: str = "Chart 7", shape_id: int = 6) -> str:
    """Build a p:graphicFrame carrying an embedded chart reference."""
    return f"""<p:graphicFrame>
<p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
<p:xfrm/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">
<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:r="{R_NS}" r:id="{rid}"/>
</a:graphicData></a:graphic>
</p:graphicFrame>"""


def chart_xml() -> str:
    """Minimal bar chart part with title and two series (2 categories each)."""
    c = "http://schemas.openxmlformats.org/drawingml/2006/chart"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"

    def series(name: str, values: str) -> str:
        v0, v1 = values.split(",")
        return (
            "<c:ser><c:tx><c:strRef><c:f>Sheet1!$B$1</c:f><c:strCache>"
            '<c:ptCount val="1"/><c:pt idx="0">'
            f"<c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>"
            "<c:cat><c:strRef><c:f>Sheet1!$A$2:$A$3</c:f><c:strCache>"
            '<c:ptCount val="2"/>'
            '<c:pt idx="0"><c:v>East</c:v></c:pt>'
            '<c:pt idx="1"><c:v>West</c:v></c:pt>'
            "</c:strCache></c:strRef></c:cat>"
            "<c:val><c:numRef><c:f>Sheet1!$B$2:$B$3</c:f><c:numCache>"
            '<c:ptCount val="2"/>'
            f'<c:pt idx="0"><c:v>{v0}</c:v></c:pt>'
            f'<c:pt idx="1"><c:v>{v1}</c:v></c:pt>'
            "</c:numCache></c:numRef></c:val></c:ser>"
        )

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="{c}" xmlns:a="{a}">
<c:chart>
<c:title><c:tx><c:rich><a:bodyPr/><a:p><a:r><a:t>Sales</a:t></a:r></a:p></c:rich></c:tx></c:title>
<c:plotArea>
<c:barChart>
<c:barDir val="col"/>
{series("Q1", "10,20")}
{series("Q2", "15,25")}
</c:barChart>
</c:plotArea>
</c:chart>
</c:chartSpace>"""


def smartart_shape_xml(*, dm_rid: str = "rId2", lo_rid: str = "rId3", name: str = "Diagram 8", shape_id: int = 6) -> str:
    """Build a p:graphicFrame carrying a diagram (SmartArt) reference."""
    dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    return f"""<p:graphicFrame>
<p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
<p:xfrm/>
<a:graphic><a:graphicData uri="{dgm}">
<dgm:relIds xmlns:dgm="{dgm}" xmlns:r="{R_NS}" r:dm="{dm_rid}" r:lo="{lo_rid}" r:qs="" r:cs=""/>
</a:graphicData></a:graphic>
</p:graphicFrame>"""


def diagram_data_xml() -> str:
    """Minimal diagram data model: 3 nodes in a chain (1→2→3)."""
    dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    mid1 = "{11111111-1111-1111-1111-111111111111}"
    mid2 = "{22222222-2222-2222-2222-222222222222}"
    mid3 = "{33333333-3333-3333-3333-333333333333}"

    def node(model_id: str, text: str) -> str:
        return (
            f'<dgm:pt modelId="{model_id}"><dgm:prSet/><dgm:t>'
            f"<a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></dgm:t></dgm:pt>"
        )

    def cxn(model_id: str, from_id: str, to_id: str) -> str:
        return f'<dgm:cxn modelId="{model_id}" fromModelId="{from_id}" toModelId="{to_id}"/>'

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<dgm:dataModel xmlns:dgm="{dgm}" xmlns:a="{a}">
<dgm:ptLst>
{node(mid1, "Start")}
{node(mid2, "Middle")}
{node(mid3, "End")}
</dgm:ptLst>
<dgm:cxnLst>
{cxn("c1", mid1, mid2)}
{cxn("c2", mid2, mid3)}
</dgm:cxnLst>
</dgm:dataModel>"""


def diagram_layout_xml() -> str:
    """Minimal diagram layout with a process category."""
    dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<dgm:layoutDef xmlns:dgm="{dgm}">
<dgm:catLst><dgm:cat type="{dgm}/process"/></dgm:catLst>
</dgm:layoutDef>"""


def table_shape_xml(rows: list[list[str]], *, name: str = "Table 3", shape_id: int = 6) -> str:
    """Build a p:graphicFrame carrying an a:tbl with one paragraph per cell."""
    grid = '<a:gridCol w="100"/>' * len(rows[0]) if rows else ""
    trs = ""
    for row in rows:
        tcs = ""
        for text in row:
            tcs += f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>"
        trs += f'<a:tr h="0">{tcs}</a:tr>'
    return f"""<p:graphicFrame>
<p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
<p:xfrm/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
<a:tbl><a:tblPr firstRow="1"/><a:tblGrid>{grid}</a:tblGrid>{trs}</a:tbl>
</a:graphicData></a:graphic>
</p:graphicFrame>"""


def rich_deck_pptx(*, with_geometry: bool = False) -> Path:
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
