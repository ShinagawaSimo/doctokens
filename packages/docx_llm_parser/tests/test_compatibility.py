"""Compatibility failures and namespace/event infrastructure.

These XML cases exercise unknown producer namespaces, malformed Requires and
unreadable choices that desktop Word cannot author reliably. Ordinary text-box
reading is verified on the original native DOCX; see the real-fixture checklist.
"""

from __future__ import annotations

from io import BytesIO
from xml.etree import ElementTree as ET

import pytest
from docx_llm_parser import parse_docx
from docx_llm_parser.core.constants import NS
from docx_llm_parser.ooxml.compatibility import DocxCompatibility

from packages.docx_llm_parser.tests.test_body_structure import _make_docx as _package

MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
DECLARATIONS = f'xmlns:mc="{MC}" xmlns:w="{NS["w"]}" xmlns:wps="{NS["wps"]}"'
PLAIN_HEADER = "density=plain format=docx pagination=last-rendered-hints revision_view=final\n<page=1>\n\n"


def _make_docx(body: str, extra: dict[str, str] | None = None) -> bytes:
    return _package(body, {"word/styles.xml": f'<w:styles xmlns:w="{NS["w"]}"/>', **(extra or {})})


def _choice(content: str, requires: str = "wps", declarations: str = "") -> str:
    return f'<mc:Choice Requires="{requires}" {declarations}>{content}</mc:Choice>'


def _alternate(choices: str, fallback: str | None = None) -> str:
    tail = "" if fallback is None else f"<mc:Fallback>{fallback}</mc:Fallback>"
    return f"<mc:AlternateContent {DECLARATIONS}>{choices}{tail}</mc:AlternateContent>"


def _read(xml: str) -> tuple[ET.Element, DocxCompatibility]:
    compatibility = DocxCompatibility([], {})
    root = compatibility.read(BytesIO(xml.encode()), "word/document.xml")
    return root, compatibility


def _run(content: str) -> str:
    return f"<w:r>{content}</w:r>"


def _paragraph(content: str) -> str:
    return f"<w:p>{_run(content)}</w:p>"


@pytest.mark.parametrize(
    ("requires", "declarations", "branch", "reason"),
    [
        ("alias", f'xmlns:alias="{NS["wps"]}"', "Choice", "supported_choice"),
        ("wps", 'xmlns:wps="urn:unknown-producer"', "Fallback", "no_supported_choice"),
        ("missing", "", "Fallback", "no_supported_choice"),
        ("", "", "Fallback", "no_supported_choice"),
        ("wps future", 'xmlns:future="urn:unknown-producer"', "Fallback", "no_supported_choice"),
    ],
)
def test_requires_uses_scoped_uris(requires: str, declarations: str, branch: str, reason: str) -> None:
    first = _alternate(_choice("<w:t>chosen</w:t>", requires, declarations), "<w:t>fallback</w:t>")
    second = _alternate(_choice("<w:t>next</w:t>"))
    root, reader = _read(f"<w:r {DECLARATIONS}>{first}{second}</w:r>")
    assert [record["branch"] for record in reader.records] == [branch, "Choice"]
    assert reader.records[0]["reason"] == reason
    assert "".join(root.itertext()) == ("chosen" if branch == "Choice" else "fallback") + "next"
    assert reader.warnings == []


def test_unknown_choice_does_not_hide_a_later_supported_choice() -> None:
    choices = _choice("<w:t>unsupported</w:t>", "future", 'xmlns:future="urn:future"')
    choices += _choice("<w:unreadable/>") + _choice("<w:t>readable</w:t>")
    root, reader = _read(f"<w:r {DECLARATIONS}>{_alternate(choices, '<w:t>fallback</w:t>')}</w:r>")
    assert ET.tostring(root, encoding="unicode") == f'<ns0:r xmlns:ns0="{NS["w"]}"><ns0:t>readable</ns0:t></ns0:r>'
    assert reader.records[0]["choiceIndex"] == 3
    assert [r["reason"] for r in reader.records[0]["rejectedChoices"]] == ["unsupported_namespace", "unprocessable_content"]


@pytest.mark.parametrize("opaque", ["<w:unknown/>", "<w:drawing/>", "<w:pict/>", "<w:object/>"])
def test_opaque_choice_uses_fallback_without_speculative_side_effects(opaque: str) -> None:
    # A rejected branch contains stateful constructs before unreadable content.
    choice = _choice('<w:lastRenderedPageBreak/><w:fldChar w:fldCharType="begin"/>' + opaque)
    xml = "<w:p>" + _run(_alternate(choice, "<w:t>visible</w:t>")) + "</w:p>"
    result = parse_docx(_make_docx(xml))
    assert result.text == (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final">'
        '<body><page number="1" /><p>visible</p></body></document>'
    )
    assert result.report.warnings == ()
    assert result.report.manifest["alternateContent"][0]["reason"] == "choice_unprocessable"


def test_nested_rejected_branch_leaves_no_diagnostics_or_selection_records() -> None:
    inner = _alternate(_choice("<w:unknown/>"))
    outer = _alternate(_choice(inner), "<w:t>fallback</w:t>")
    result = parse_docx(_make_docx("<w:p>" + _run(outer) + "</w:p>"), density="plain")
    assert result.text == PLAIN_HEADER + "fallback"
    assert result.report.warnings == ()
    assert len(result.report.manifest["alternateContent"]) == 1


def test_nested_selected_fallback_preserves_order_and_part_ordinals() -> None:
    inner = _alternate(_choice("<w:unknown/>"), "<w:t>middle</w:t>")
    outer = _alternate(_choice("<w:t>before</w:t>" + inner + "<w:t>after</w:t>"), "<w:t>unused</w:t>")
    root, reader = _read(f"<w:r {DECLARATIONS}>{outer}</w:r>")
    assert "".join(root.itertext()) == "beforemiddleafter"
    assert [(r["index"], r["branch"]) for r in reader.records] == [(1, "Choice"), (2, "Fallback")]


def test_unresolvable_alternate_is_reported_once() -> None:
    xml = "<w:p>" + _run(_alternate(_choice("<w:unknown/>"))) + "</w:p>"
    result = parse_docx(_make_docx(xml))
    assert [w.code for w in result.report.warnings] == ["ALTERNATE_CONTENT_UNRESOLVED"]
    assert result.report.warnings[0].locator == "word/document.xml:AlternateContent[1]"
    assert result.report.manifest["alternateContent"][0]["branch"] == "none"


def test_empty_selected_branch_does_not_resurrect_fallback() -> None:
    # Selection metadata is an API contract even when no body content is emitted.
    root, reader = _read(f"<w:r {DECLARATIONS}>{_alternate(_choice(''), '<w:t>unused</w:t>')}</w:r>")
    assert list(root) == []
    assert reader.records[0]["branch"] == "Choice"


def test_body_replay_survives_consumer_clearing_completed_elements() -> None:
    # Unknown producer choices force fallback at the streaming block boundary.
    choices = _choice("<future:object xmlns:future='urn:future'/>", "future", "xmlns:future='urn:future'")
    fallback = _paragraph("<w:t>one</w:t>") + _paragraph("<w:t>two</w:t>")
    result = parse_docx(_make_docx(_alternate(choices, fallback) + _paragraph("<w:t>three</w:t>")), density="plain")
    assert result.text == PLAIN_HEADER + "one\n\ntwo\n\nthree"
    assert result.report.warnings == ()


def test_ancillary_reader_uses_same_fallback_contract() -> None:
    alternate = _alternate(_choice("<w:unknown/>"), _run("<w:t>header</w:t>"))
    header = f'<w:hdr xmlns:w="{NS["w"]}"><w:p>{alternate}</w:p></w:hdr>'
    result = parse_docx(_make_docx(_paragraph("<w:t>body</w:t>"), {"word/header1.xml": header}))
    assert result.text == (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final">'
        '<body><page number="1" /><p>body</p></body>'
        '<supplemental><headers><header id="header1" locator="headers.header1">header</header>'
        "</headers></supplemental></document>"
    )
    assert result.report.manifest["alternateContent"][0]["part"] == "word/header1.xml"


def test_unknown_drawing_extension_falls_back_inside_textbox_without_duplication() -> None:
    # The future producer extension is intentionally not readable by this parser.
    nested = _alternate(_choice("<w:futureText/>", "future", 'xmlns:future="urn:future"'), "<w:t>caption</w:t>")
    textbox = f'<wps:txbx xmlns:wps="{NS["wps"]}"><w:txbxContent>{_paragraph(nested)}</w:txbxContent></wps:txbx>'
    outer = _alternate(_choice(f"<w:drawing>{textbox}</w:drawing>"), "<w:t>unused</w:t>")
    result = parse_docx(_make_docx("<w:p>" + _run(outer) + "</w:p>"))
    assert result.text == (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final">'
        '<body><page number="1" /><p><textbox>caption</textbox></p></body></document>'
    )
    assert [(r["index"], r["branch"]) for r in result.report.manifest["alternateContent"]] == [(1, "Choice"), (2, "Fallback")]


def test_unsupported_choice_in_table_keeps_fallback_in_original_cell() -> None:
    content = _alternate(_choice("<w:unknown/>"), "<w:t>cell</w:t>")
    table = f"<w:tbl><w:tr><w:tc><w:tcPr/>{_paragraph(content)}</w:tc></w:tr></w:tbl>"
    result = parse_docx(_make_docx(table), density="plain")
    assert result.text == PLAIN_HEADER + "cell"
    assert result.report.warnings == ()
