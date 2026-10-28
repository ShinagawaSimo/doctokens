"""Temporary formula-view regressions pending native equation/revision files.

Reuse the existing migration package helper. Replace normal-content assertions
when the listed Office fixtures and their reviewed full goldens exist.
"""

from __future__ import annotations

import pytest
from _word_packages import _make_docx
from doctokens_word import open_docx, parse_docx
from doctokens_word.docx.model import ParseOptions

_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_FRACTION = "<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f>"
_BODY = (
    f'<w:p><m:oMath xmlns:m="{_M}"><m:r><m:t>2+</m:t></m:r>'
    '<w:del w:author="Old"><m:r><w:delText>x</w:delText></m:r></w:del>'
    f'<w:ins w:author="New">{_FRACTION}</w:ins></m:oMath></w:p>'
    f'<w:p><w:del w:author="Old"><m:oMath xmlns:m="{_M}">{_FRACTION}</m:oMath></w:del></w:p>'
)
_FINAL = r'<p><equation notation="latex">2+\frac{a}{b}</equation></p>'
_ORIGINAL = r'<p><equation notation="latex">2+x</equation></p><p><equation notation="latex">\frac{a}{b}</equation></p>'
_REVIEW = r'<p><equation notation="latex">2+x\frac{a}{b}</equation></p><p><equation notation="latex">\frac{a}{b}</equation></p>'
_SEMANTIC_REVIEW = (
    r'<p><equation notation="latex">2+<del author="Old">x</del><ins author="New">\frac{a}{b}</ins></equation></p>'
    r'<p><del author="Old"><equation notation="latex">\frac{a}{b}</equation></del></p>'
)


@pytest.mark.parametrize("mode", ["final", "original", "review"])
@pytest.mark.parametrize("density", ["plain", "structural", "semantic"])
def test_math_view_complete_reading_output(mode: str, density: str) -> None:
    source = _make_docx(_BODY)
    options = ParseOptions(revision_mode=mode)
    actual = parse_docx(source, density=density, options=options).text
    if density == "plain":
        body = {
            "final": r"2+\frac{a}{b}",
            "original": "2+x\n\n" + r"\frac{a}{b}",
            "review": r"2+x\frac{a}{b}" + "\n\n" + r"\frac{a}{b}",
        }[mode]
        expected = f"density=plain format=docx pagination=last-rendered-hints revision_view={mode}\n<page=1>\n\n{body}"
    else:
        body = {"final": _FINAL, "original": _ORIGINAL, "review": _SEMANTIC_REVIEW if density == "semantic" else _REVIEW}[mode]
        expected = (
            f'<document density="{density}" format="docx" pagination="last-rendered-hints" revision-view="{mode}">'
            f'<body><page number="1" />{body}</body></document>'
        )
    assert actual == expected
    with open_docx(source, options=options) as session:
        assert session.render(density=density).text == expected


@pytest.mark.parametrize("revision", ["ins", "del", "moveTo", "moveFrom"])
def test_whole_equation_revision_wraps_object(revision: str) -> None:
    source = _make_docx(
        f'<w:p><w:{revision} w:author="Editor"><m:oMath xmlns:m="{_M}">{_FRACTION}</m:oMath></w:{revision}></w:p>'
    )
    tag = "ins" if revision in {"ins", "moveTo"} else "del"
    expected = (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="review">'
        f'<body><page number="1" /><p><{tag} author="Editor"><equation notation="latex">'
        rf"\frac{{a}}{{b}}</equation></{tag}></p></body></document>"
    )
    assert parse_docx(source, options=ParseOptions(revision_mode="review")).text == expected


def test_math_unknown_extension_exposes_diagnostic() -> None:
    # A producer-specific unknown namespace is an exceptional input.
    source = _make_docx(
        f'<w:p><m:oMath xmlns:m="{_M}" xmlns:u="urn:future"><u:math><m:r><m:t>a_b</m:t></m:r></u:math></m:oMath></w:p>'
    )
    result = parse_docx(source)
    assert [warning.code for warning in result.report.warnings if warning.code.startswith("MATH_")] == [
        "MATH_CONTENT_UNSUPPORTED"
    ]
