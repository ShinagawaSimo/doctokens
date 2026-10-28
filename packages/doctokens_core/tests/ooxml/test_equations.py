"""Temporary OMML regressions pending the docx-equation-* native files.

Replaces the Word renderer's former compound converter test, which used
nonstandard property paths. These normal-content cases remain a migration gap
listed in docs/真实测试文件清单.md, not permanent substitutes for native files.
"""

from xml.etree import ElementTree as ET

import pytest
from doctokens_core.ooxml.equations.converter import omath_to_latex

_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


@pytest.mark.parametrize(
    ("xml", "expected"),
    [
        (
            '<m:nary><m:naryPr><m:chr m:val="∏"/></m:naryPr><m:sub><m:r><m:t>k=1</m:t></m:r></m:sub>'
            "<m:sup><m:r><m:t>n</m:t></m:r></m:sup><m:e><m:r><m:t>A</m:t></m:r></m:e></m:nary>",
            r"\prod_{k=1}^{n} {A}",
        ),
        ("<m:nary><m:sub/><m:sup/><m:e><m:r><m:t>f</m:t></m:r></m:e></m:nary>", r"\int {f}"),
        (
            '<m:nary><m:naryPr><m:chr m:val="∫"/><m:subHide/><m:supHide m:val="false"/></m:naryPr>'
            "<m:sub><m:r><m:t>0</m:t></m:r></m:sub><m:sup><m:r><m:t>1</m:t></m:r></m:sup>"
            "<m:e><m:r><m:t>f</m:t></m:r></m:e></m:nary>",
            r"\int^{1} {f}",
        ),
        (
            "<m:nary><m:naryPr><m:chr/></m:naryPr><m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
            "<m:sup/><m:e><m:r><m:t>x</m:t></m:r></m:e></m:nary>",
            r"{}_{i} {x}",
        ),
        ('<m:acc><m:accPr><m:chr m:val="⃗"/></m:accPr><m:e><m:r><m:t>v</m:t></m:r></m:e></m:acc>', r"\vec{v}"),
        ('<m:acc><m:accPr><m:chr m:val="̈"/></m:accPr><m:e><m:r><m:t>a</m:t></m:r></m:e></m:acc>', r"\ddot{a}"),
        ("<m:acc><m:accPr><m:chr/></m:accPr><m:e><m:r><m:t>v</m:t></m:r></m:e></m:acc>", "v"),
        ("<m:acc><m:e><m:r><m:t>v</m:t></m:r></m:e></m:acc>", r"\hat{v}"),
        ('<m:bar><m:barPr><m:pos m:val="bot"/></m:barPr><m:e><m:r><m:t>q</m:t></m:r></m:e></m:bar>', r"\underline{q}"),
        ('<m:bar><m:barPr><m:pos m:val="top"/></m:barPr><m:e><m:r><m:t>q</m:t></m:r></m:e></m:bar>', r"\overline{q}"),
        ("<m:bar><m:e><m:r><m:t>q</m:t></m:r></m:e></m:bar>", r"\underline{q}"),
        (
            '<m:d><m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/><m:sepChr m:val=";"/></m:dPr>'
            "<m:e><m:r><m:t>x</m:t></m:r></m:e><m:e><m:r><m:t>y</m:t></m:r></m:e></m:d>",
            r"\left[ x;y \right]",
        ),
        ("<m:d><m:e><m:r><m:t>x</m:t></m:r></m:e><m:e><m:r><m:t>y</m:t></m:r></m:e></m:d>", r"\left( x|y \right)"),
        (
            '<m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val=""/><m:sepChr/></m:dPr>'
            "<m:e><m:r><m:t>x</m:t></m:r></m:e><m:e><m:r><m:t>y</m:t></m:r></m:e></m:d>",
            r"\left\{ xy \right.",
        ),
        (
            '<m:groupChr><m:groupChrPr><m:chr m:val="⏞"/><m:pos m:val="top"/></m:groupChrPr>'
            "<m:e><m:r><m:t>a+b</m:t></m:r></m:e></m:groupChr>",
            r"\overbrace{a+b}",
        ),
        ("<m:groupChr><m:e><m:r><m:t>a+b</m:t></m:r></m:e></m:groupChr>", r"\underbrace{a+b}"),
        (
            "<m:func><m:fName><m:limLow><m:e><m:r><m:t>lim</m:t></m:r></m:e>"
            "<m:lim><m:r><m:t>x→0</m:t></m:r></m:lim></m:limLow></m:fName><m:e><m:r><m:t>f</m:t></m:r></m:e></m:func>",
            r"\lim_{x→0}{f}",
        ),
        (
            "<m:func><m:fName><m:r><m:t>sin</m:t></m:r></m:fName><m:e><m:r><m:t>x</m:t></m:r></m:e></m:func>",
            r"\sin{x}",
        ),
        (
            "<m:r><m:t>x</m:t></m:r><m:sPre><m:e><m:r><m:t>A</m:t></m:r></m:e>"
            "<m:sub><m:r><m:t>l</m:t></m:r></m:sub><m:sup><m:r><m:t>u</m:t></m:r></m:sup></m:sPre>",
            r"x{}_{l}^{u}A",
        ),
        (
            "<m:f><m:num><m:r><m:t>a&amp;b</m:t></m:r></m:num><m:den><m:r><m:t>c_d</m:t></m:r></m:den></m:f>",
            r"\frac{a\&b}{c\_d}",
        ),
        ("<m:rad><m:deg><m:r><m:t>3</m:t></m:r></m:deg><m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad>", r"\sqrt[3]{x}"),
        ("<m:sSub><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub>", r"x_{i}"),
        ("<m:sSup><m:e><m:r><m:t>y</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>", r"y^{2}"),
        (
            "<m:sSubSup><m:e><m:r><m:t>z</m:t></m:r></m:e><m:sub><m:r><m:t>0</m:t></m:r></m:sub>"
            "<m:sup><m:r><m:t>n</m:t></m:r></m:sup></m:sSubSup>",
            r"z_{0}^{n}",
        ),
        (
            "<m:m><m:mr><m:e><m:r><m:t>1</m:t></m:r></m:e><m:e><m:r><m:t>2</m:t></m:r></m:e></m:mr></m:m>",
            r"\begin{matrix} 1 & 2 \end{matrix}",
        ),
        (
            "<m:eqArr><m:e><m:r><m:t>x=1</m:t></m:r></m:e><m:e><m:r><m:t>y=2</m:t></m:r></m:e></m:eqArr>",
            r"\begin{aligned} x=1 \\ y=2 \end{aligned}",
        ),
        ("<m:limLow><m:e><m:r><m:t>h</m:t></m:r></m:e><m:lim><m:r><m:t>0</m:t></m:r></m:lim></m:limLow>", r"{h}_{0}"),
        ("<m:limUpp><m:e><m:r><m:t>h</m:t></m:r></m:e><m:lim><m:r><m:t>∞</m:t></m:r></m:lim></m:limUpp>", r"{h}^{∞}"),
        ("<m:phant><m:e><m:r><m:t>ghost</m:t></m:r></m:e></m:phant>", r"\phantom{ghost}"),
        ("<m:borderBox><m:e><m:r><m:t>box</m:t></m:r></m:e></m:borderBox>", r"\boxed{box}"),
        ("<m:box><m:e><m:r><m:t>pass</m:t></m:r></m:e></m:box>", "pass"),
        ("<m:r><m:t>\\{a}_b</m:t></m:r>", r"\textbackslash{}\{a\}\_b"),
    ],
)
def test_saved_math_structure(xml: str, expected: str) -> None:
    expression = ET.fromstring(f'<m:oMath xmlns:m="{_M}">{xml}</m:oMath>')
    assert omath_to_latex(expression) == expected


def test_unknown_math_extension_preserves_escaped_text() -> None:
    # Unknown extensions cannot be authored reliably in an ordinary Office file.
    expression = ET.fromstring(f'<m:oMath xmlns:m="{_M}"><m:unknown><m:r><m:t>a_b</m:t></m:r></m:unknown></m:oMath>')
    assert omath_to_latex(expression) == r"a\_b"
