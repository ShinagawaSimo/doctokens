"""Damaged comment parts; normal content requires native files and reviewed goldens."""

from __future__ import annotations

import pytest
from _pptx_package import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
)
from doctokens_powerpoint import parse_pptx

_MODERN = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"


def _damaged_comments(body: str | None) -> bytes:
    # Missing/malformed parts and an invalid extension root cannot be created
    # through the normal PowerPoint comment UI.
    entries = {
        "[Content_Types].xml": content_types_xml(1),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(""),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(
            '<Relationship Id="c" Type="http://schemas.microsoft.com/office/2018/10/relationships/comments" '
            'Target="../comments/modern.xml"/>'
        ),
    }
    if body is not None:
        entries["ppt/comments/modern.xml"] = body
    return make_pptx(entries)


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (None, "COMMENTS_PART_MISSING"),
        ("<broken", "COMMENTS_XML_INVALID"),
        ("<future/>", "COMMENTS_ROOT_UNSUPPORTED"),
        (f'<cmLst xmlns="{_MODERN}"><future:cm xmlns:future="urn:future"/></cmLst>', "COMMENT_ELEMENT_UNSUPPORTED"),
    ],
)
def test_unreadable_comment_part_retains_a_placeholder(body: str | None, code: str) -> None:
    result = parse_pptx(_damaged_comments(body), density="semantic")
    assert code in [warning.code for warning in result.report.warnings]
    assert result.text == (
        '<presentation density="semantic" format="pptx"><slide number="1"><comment-ref id="cmt1" /></slide>'
        '<comments><comment id="cmt1" slide="slide1"><unsupported type="comments" /></comment></comments></presentation>'
    )


def test_invalid_comment_status_does_not_hide_the_comment() -> None:
    # An arbitrary enum value is invalid XML content, not a normal UI state.
    source = _damaged_comments(f'<cmLst xmlns="{_MODERN}"><cm id="a" authorId="b" status="future"/></cmLst>')
    result = parse_pptx(source, density="structural")
    assert "COMMENT_STATUS_INVALID" in [warning.code for warning in result.report.warnings]
    assert result.text == (
        '<presentation density="structural" format="pptx"><slide number="1"><comment-ref id="cmt1" /></slide>'
        '<comments><comment author="" id="cmt1" slide="slide1" /></comments></presentation>'
    )
