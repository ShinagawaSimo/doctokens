"""Unreadable extensions and corrupt bodies, impossible to save through normal Office UI."""

from __future__ import annotations

import pytest
from _pptx_package import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    rich_text_shape_xml,
    root_rels_xml,
    slide_xml_shapes,
)
from doctokens_powerpoint import parse_pptx

_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _damaged_deck(shapes: str) -> bytes:
    return make_pptx(
        {
            "[Content_Types].xml": content_types_xml(1),
            "_rels/.rels": root_rels_xml(),
            "ppt/presentation.xml": presentation_xml(1),
            "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
            "ppt/slides/slide1.xml": slide_xml_shapes(shapes),
        }
    )


@pytest.mark.parametrize(
    ("shapes", "source", "code"),
    [
        (
            f'<mc:AlternateContent xmlns:mc="{_MC}"><mc:Choice Requires="missing"><p:sp/></mc:Choice></mc:AlternateContent>',
            "AlternateContent",
            "SHAPE_ALTERNATE_CONTENT_UNSUPPORTED",
        ),
        (
            '<p:graphicFrame><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"/>'
            "</a:graphic></p:graphicFrame>",
            "graphicFrame",
            "TABLE_MISSING_TBL",
        ),
    ],
)
def test_unreadable_shape_remains_in_every_density(shapes: str, source: str, code: str) -> None:
    data = _damaged_deck(shapes)
    for density in ("plain", "structural", "semantic"):
        result = parse_pptx(data, density=density)
        assert code in [item.code for item in result.report.warnings]
        expected = (
            f"density=plain format=pptx\n=== Slide 1 ===\n[Unparsed shape: {source}]"
            if density == "plain"
            else f'<presentation density="{density}" format="pptx"><slide number="1">'
            f'<unsupported shape-id="s1" source="{source}" type="shape" /></slide></presentation>'
        )
        assert result.text == expected


def test_unreadable_math_retains_its_inline_position() -> None:
    paragraph = (
        "<a:r><a:t>Before</a:t></a:r>"
        f'<mc:AlternateContent xmlns:mc="{_MC}" xmlns:m="{_M}"><mc:Choice Requires="missing">'
        "<m:oMath/></mc:Choice></mc:AlternateContent><a:r><a:t>After</a:t></a:r>"
    )
    source = _damaged_deck(rich_text_shape_xml([paragraph], name="Box"))
    for density in ("plain", "structural", "semantic"):
        result = parse_pptx(source, density=density)
        expected = (
            "density=plain format=pptx\n=== Slide 1 ===\nBefore[Unparsed equation]After"
            if density == "plain"
            else f'<presentation density="{density}" format="pptx"><slide number="1"><p'
            + (' name="Box"' if density == "semantic" else "")
            + ' shape-id="s1">Before<unsupported type="equation" />After</p></slide></presentation>'
        )
        assert result.text == expected


def test_invalid_baseline_keeps_readable_text_without_an_element_placeholder() -> None:
    source = _damaged_deck(
        rich_text_shape_xml(
            ['<a:r><a:rPr baseline="invalid"/><a:t>Readable</a:t></a:r>'],
            name="Box",
        )
    )
    result = parse_pptx(source, density="semantic")
    assert "TEXT_BASELINE_INVALID" in [item.code for item in result.report.warnings]
    assert result.text == (
        '<presentation density="semantic" format="pptx"><slide number="1">'
        '<p name="Box" shape-id="s1">Readable</p></slide></presentation>'
    )
