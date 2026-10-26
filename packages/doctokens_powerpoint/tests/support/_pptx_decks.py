"""Existing composite PPTX setup pending native presentation files."""

from __future__ import annotations

from _pptx_namespaces import PNG_BYTES, R_NS
from _pptx_objects import chart_shape_xml, chart_xml, diagram_data_xml, diagram_layout_xml, smartart_shape_xml, table_shape_xml
from _pptx_package import (
    comment_authors_xml,
    comments_xml,
    content_types_xml,
    make_pptx,
    media_shape_xml,
    notes_slide_xml,
    picture_shape_xml,
    presentation_rels_xml,
    presentation_xml,
    rich_text_shape_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    text_shape_xml,
)


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
