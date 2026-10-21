"""Story isolation and preservation around dangling VML producer references.

Normal atomic text-box fixtures remain in the existing checklist. These cases
include a dangling image reference or excessive nesting that Word cannot save
reliably, and compare the complete resulting XML rather than internal IR.
"""

from __future__ import annotations

import pytest
from docx_llm_parser import open_docx, parse_docx

from packages.docx_llm_parser.tests.test_vml_images import DECLARATIONS, REL_NS, _abnormal_docx


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


@pytest.mark.parametrize("density", ["structural", "semantic"])
def test_textbox_table_images_and_links_do_not_consume_outer_field_state(density: str) -> None:
    story = (
        "<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Note</w:t></w:r>"
        '<w:hyperlink r:id="link"><w:r><w:t> Link</w:t></w:r></w:hyperlink></w:p>'
        "<w:tbl><w:tr><w:tc>" + _paragraph("A") + "</w:tc><w:tc><w:p/></w:tc><w:tc>" + _paragraph("C") + "</w:tc></w:tr></w:tbl>"
        f'<w:p><w:r><w:pict {DECLARATIONS}><v:shape alt="Inner"><v:imagedata r:id="image"/>'
        '</v:shape><v:shape><v:imagedata r:id="missing"/></v:shape></w:pict></w:r></w:p>'
    )
    body = (
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText>HYPERLINK "https://outer.test"</w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Before</w:t></w:r>'
        '<w:r><w:drawing xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        "<wps:txbx><w:txbxContent>" + story + "</w:txbxContent></wps:txbx></w:drawing></w:r>"
        '<w:r><w:t>After</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
        "<w:tbl><w:tr><w:tc>" + _paragraph("Outside") + "</w:tc></w:tr></w:tbl>"
    )
    relationships = (
        f'<Relationships xmlns="{REL_NS}"><Relationship Id="image" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/valid.png"/>'
        '<Relationship Id="link" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        'Target="https://inner.test" TargetMode="External"/></Relationships>'
    )
    source = _abnormal_docx(body, {"word/_rels/document.xml.rels": relationships})
    note = "<b>Note</b>" if density == "semantic" else "Note"
    image = '<img alt="Inner" id="img1" />' if density == "semantic" else '<img id="img1" />'
    expected = (
        f'<document density="{density}" format="docx" pagination="last-rendered-hints" revision-view="final">'
        '<body><page number="1" /><p><a href="https://outer.test">Before</a><textbox>'
        f'<p>{note}<a href="https://inner.test"> Link</a></p>'
        '<table id="t1"><tr><td><p>A</p></td><td /><td><p>C</p></td></tr></table>'
        f'<p>{image}<img /></p></textbox><a href="https://outer.test">After</a></p>'
        '<table id="t2"><tr><td><p>Outside</p></td></tr></table></body><assets><img id="img1" /></assets></document>'
    )
    assert parse_docx(source, density=density).text == expected
    with open_docx(source) as document:
        assert document.render_resource("table", "t1").text == (
            '<document density="semantic" format="docx"><resources><table cols="3" id="t1" rows="1">'
            "<tr><td>A</td><td /><td>C</td></tr></table></resources></document>"
        )


def test_excessive_textbox_nesting_has_an_explicit_diagnostic() -> None:
    story = _paragraph("Deep")
    for _ in range(34):
        story = (
            f"<w:p><w:r><w:pict {DECLARATIONS}><v:shape><v:textbox><w:txbxContent>{story}"
            "</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>"
        )
    result = parse_docx(_abnormal_docx(story, {}, with_image=False))
    assert [warning.code for warning in result.report.warnings] == ["TEXTBOX_NESTING_LIMIT"]
