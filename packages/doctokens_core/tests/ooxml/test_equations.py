"""Temporary OMML regressions pending the docx-equation-* native files.

Replaces the Word renderer's former compound converter test, which used
nonstandard property paths. These normal-content cases remain a migration gap
listed in docs/真实测试文件清单.md, not permanent substitutes for native files.
"""

from xml.etree import ElementTree as ET

import pytest
from doctokens_core.ooxml.equations.converter import convert_math
from doctokens_core.ooxml.equations.results import append_math_text

_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


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
        ("<m:phant><m:e><m:r><m:t>ghost</m:t></m:r></m:e></m:phant>", "ghost"),
        ("<m:borderBox><m:e><m:r><m:t>box</m:t></m:r></m:e></m:borderBox>", r"\boxed{box}"),
        ("<m:box><m:e><m:r><m:t>pass</m:t></m:r></m:e></m:box>", "pass"),
        ("<m:r><m:t>\\{a}_b</m:t></m:r>", r"\textbackslash{}\{a\}\_b"),
        (
            '<m:f><m:fPr><m:type m:val="noBar"/></m:fPr><m:num><m:r><m:t>n</m:t></m:r></m:num>'
            "<m:den><m:r><m:t>k</m:t></m:r></m:den></m:f>",
            r"\genfrac{}{}{0pt}{}{n}{k}",
        ),
        (
            "<m:rad><m:radPr><m:degHide/></m:radPr><m:deg><m:r><m:t>3</m:t></m:r></m:deg>"
            "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad>",
            r"\sqrt{x}",
        ),
        (
            '<m:rad><m:radPr><m:degHide m:val="false"/></m:radPr><m:deg><m:r><m:t>3</m:t></m:r></m:deg>'
            "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad>",
            r"\sqrt[3]{x}",
        ),
        ('<m:phant><m:phantPr><m:show m:val="false"/></m:phantPr><m:e><m:r><m:t>x</m:t></m:r></m:e></m:phant>', r"\phantom{x}"),
        ("<m:phant><m:phantPr><m:show/></m:phantPr><m:e><m:r><m:t>x</m:t></m:r></m:e></m:phant>", "x"),
        (
            "<m:borderBox><m:borderBoxPr><m:hideTop/><m:hideBot/><m:hideLeft/><m:hideRight/>"
            "<m:strikeBLTR/></m:borderBoxPr><m:e><m:r><m:t>x</m:t></m:r></m:e></m:borderBox>",
            r"\cancel{x}",
        ),
        (
            "<m:borderBox><m:borderBoxPr><m:hideTop/><m:hideBot/><m:hideLeft/><m:hideRight/>"
            "<m:strikeTLBR/><m:strikeBLTR/></m:borderBoxPr><m:e><m:r><m:t>x</m:t></m:r></m:e></m:borderBox>",
            r"\xcancel{x}",
        ),
        (
            "<m:borderBox><m:borderBoxPr><m:hideTop/><m:hideBot/><m:hideLeft/><m:hideRight/>"
            "<m:strikeH/></m:borderBoxPr><m:e><m:r><m:t>x</m:t></m:r></m:e></m:borderBox>",
            r"\overset{\text{horizontal strike}}{x}",
        ),
        (
            "<m:borderBox><m:borderBoxPr><m:hideBot/><m:hideRight/></m:borderBoxPr>"
            "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:borderBox>",
            r"\left\lvert \overline{x} \right.",
        ),
        ('<m:r><m:rPr><m:scr m:val="double-struck"/></m:rPr><m:t>R+C+Z</m:t></m:r>', "ℝ+ℂ+ℤ"),
        ('<m:r><m:rPr><m:scr m:val="fraktur"/></m:rPr><m:t>g+H</m:t></m:r>', "𝔤+ℌ"),
        ('<m:r><m:rPr><m:scr m:val="script"/></m:rPr><m:t>e+R</m:t></m:r>', "ℯ+ℛ"),
        ('<m:r><m:rPr><m:sty m:val="b"/></m:rPr><m:t>v</m:t></m:r>', r"\mathbf{v}"),
        ('<m:r><m:rPr><m:nor/></m:rPr><m:t xml:space="preserve">if x &gt; 0</m:t></m:r>', r"\text{if x > 0}"),
        (
            '<m:func><m:fName><m:acc><m:accPr><m:chr m:val="̂"/></m:accPr><m:e><m:r><m:t>f</m:t></m:r></m:e>'
            "</m:acc></m:fName><m:e><m:r><m:t>x</m:t></m:r></m:e></m:func>",
            r"\hat{f}{x}",
        ),
        (
            "<m:func><m:fName><m:sSup><m:e><m:sSup><m:e><m:r><m:t>f</m:t></m:r></m:e>"
            "<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:e><m:sup><m:r><m:t>3</m:t></m:r></m:sup>"
            "</m:sSup></m:fName><m:e><m:r><m:t>x</m:t></m:r></m:e></m:func>",
            r"{\operatorname{f}^{2}}^{3}{x}",
        ),
        (
            '<w:hyperlink w:anchor="Target"><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>'
            "<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></w:hyperlink>",
            r"\frac{a}{b}",
        ),
        (
            '<w:sdt><w:sdtPr><w:tag w:val="metadata"/></w:sdtPr><w:sdtContent><m:f>'
            "<m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></w:sdtContent></w:sdt>",
            r"\frac{a}{b}",
        ),
        ("<m:r><m:t>x=1</m:t><w:br/><m:t>y=2</m:t></m:r>", r"\begin{gathered} x=1 \\ y=2 \end{gathered}"),
        (
            "<m:eqArr><m:e><m:r><m:t>x&amp;=1</m:t></m:r></m:e><m:e><m:r><m:t>y&amp;=2</m:t></m:r></m:e></m:eqArr>",
            r"\begin{aligned} x&=1 \\ y&=2 \end{aligned}",
        ),
        (
            "<m:eqArr><m:e><m:r><m:t>x&amp;</m:t></m:r><m:r><m:t>&amp;=1</m:t></m:r></m:e></m:eqArr>",
            r"\begin{aligned} x&=1 \end{aligned}",
        ),
        (
            '<m:eqArr><m:e><m:r><m:rPr><m:sty m:val="b"/></m:rPr><m:t>x&amp;=1</m:t></m:r></m:e>'
            "<m:e><m:r><m:rPr><m:nor/></m:rPr><m:t>A&amp;B</m:t></m:r></m:e></m:eqArr>",
            r"\begin{aligned} \mathbf{x}&\mathbf{=1} \\ \text{A\&B} \end{aligned}",
        ),
        ("<m:r><m:t>A</m:t><w:noBreakHyphen/><m:t>B</m:t></m:r>", r"A\text{-}B"),
        ('<m:r><w:sym w:font="Symbol" w:char="F061"/></m:r>', "α"),
        ('<m:r><w:sym w:font="Symbol" w:char="F043"/></m:r>', "Χ"),
    ],
)
def test_saved_math_structure(xml: str, expected: str) -> None:
    expression = ET.fromstring(f'<m:oMath xmlns:m="{_M}" xmlns:w="{_W}">{xml}</m:oMath>')
    assert convert_math(expression).text == expected


def test_unknown_math_extension_preserves_escaped_text() -> None:
    # Unknown extensions cannot be authored reliably in an ordinary Office file.
    expression = ET.fromstring(f'<m:oMath xmlns:m="{_M}"><m:unknown><m:r><m:t>a_b</m:t></m:r></m:unknown></m:oMath>')
    assert convert_math(expression).text == r"a\_b"


def test_math_paragraph_keeps_expression_boundaries() -> None:
    expression = ET.fromstring(
        f'<m:oMathPara xmlns:m="{_M}"><m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath>'
        "<m:oMath><m:r><m:t>y=2</m:t></m:r></m:oMath></m:oMathPara>"
    )
    assert convert_math(expression).text == r"\begin{gathered} x=1 \\ y=2 \end{gathered}"


def test_nested_review_ranges_keep_equation_text_and_attribution() -> None:
    expression = ET.fromstring(
        f'<m:oMath xmlns:m="{_M}" xmlns:w="{_W}"><m:f><m:num>'
        '<w:ins w:author="A&amp;B"><w:del w:author="C"><m:r><w:delText>x</w:delText></m:r></w:del></w:ins>'
        "</m:num><m:den><m:r><m:t>y</m:t></m:r></m:den></m:f></m:oMath>"
    )
    result = convert_math(expression, revision_mode="review")
    output = ET.Element("equation")
    append_math_text(output, result.text, result.revisions)
    assert (
        ET.tostring(output, encoding="unicode")
        == r'<equation>\frac{<ins author="A&amp;B"><del author="C">x</del></ins>}{y}</equation>'
    )


def test_unknown_symbol_reports_incomplete_content() -> None:
    # Unknown/private font encodings cannot be reliably produced or decoded as Unicode.
    expression = ET.fromstring(
        f'<m:oMath xmlns:m="{_M}" xmlns:w="{_W}"><m:r><w:sym w:font="Unknown" w:char="F061"/></m:r></m:oMath>'
    )
    warnings: list[str] = []
    result = convert_math(expression, warn=lambda code, _message: warnings.append(code))
    assert (result.text, warnings) == ("", ["MATH_SYMBOL_UNSUPPORTED"])
