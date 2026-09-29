"""OMML (Office Math Markup Language) → LaTeX converter.

Recursively converts formula subtrees in Word documents to standard
LaTeX math expressions. Covers about 25 OMML element kinds: fractions,
radicals, sub/superscripts, n-ary operators, accents, function names,
bracket groups, matrices, equation arrays, limits, phantoms, etc.
"""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from ._omml_support import (
    _ACCENT_MAP,
    _DELIM_MAP,
    _FUNC_MAP,
    _NARY_OPERATOR_MAP,
    _escape_latex,
    _plain_text,
    _wrap_group,
    attr,
    child_elements,
    first_child,
    qualified_name,
)
from .xml import local_name


def omath_to_latex(elem: ET.Element) -> str:
    """Convert an OMML equation element tree to a LaTeX string."""
    return _convert_children(elem)


def _convert_node(node: ET.Element) -> str:
    """Dispatch to the handler for the node's tag name."""
    lname = local_name(node.tag)
    handler = _DISPATCH.get(lname)
    if handler is not None:
        return handler(node)
    # Unknown element: fall back to extracting its text
    return _plain_text(node)


# ── Leaf nodes: math text runs ──


def _handle_r(elem: ET.Element) -> str:
    """Handle <m:r>: extract formatted text and escape LaTeX special characters."""
    parts: list[str] = []
    for child in elem:
        if local_name(child.tag) == "t":
            text = child.text or ""
            parts.append(_escape_latex(text))
    return "".join(parts)


def _handle_t(elem: ET.Element) -> str:
    """Handle <m:t> (may be hit directly during recursive calls)."""
    return _escape_latex(elem.text or "")


# ── Fractions ──


def _handle_f(elem: ET.Element) -> str:
    """Handle <m:f> → \\frac{num}{den}."""
    num = _child_convert(elem, "num")
    den = _child_convert(elem, "den")
    return rf"\frac{{{num}}}{{{den}}}"


# ── Radicals ──


def _handle_rad(elem: ET.Element) -> str:
    """Handle <m:rad> → \\sqrt[deg]{e}."""
    deg = _child_convert(elem, "deg")
    e_val = _child_convert(elem, "e")
    if deg:
        return rf"\sqrt[{deg}]{{{e_val}}}"
    return rf"\sqrt{{{e_val}}}"


# ── Sub/superscripts ──


def _handle_ssub(elem: ET.Element) -> str:
    """Handle <m:sSub> → {e}_{sub}."""
    e_val = _child_convert(elem, "e")
    sub = _child_convert(elem, "sub")
    e_out = _wrap_group(e_val)
    return f"{e_out}_{{{sub}}}"


def _handle_ssup(elem: ET.Element) -> str:
    """Handle <m:sSup> → {e}^{sup}."""
    e_val = _child_convert(elem, "e")
    sup = _child_convert(elem, "sup")
    e_out = _wrap_group(e_val)
    return f"{e_out}^{{{sup}}}"


def _handle_ssubsup(elem: ET.Element) -> str:
    """Handle <m:sSubSup> → {e}_{sub}^{sup}."""
    e_val = _child_convert(elem, "e")
    sub = _child_convert(elem, "sub")
    sup = _child_convert(elem, "sup")
    e_out = _wrap_group(e_val)
    result = e_out
    if sub:
        result += f"_{{{sub}}}"
    if sup:
        result += f"^{{{sup}}}"
    return result


def _handle_spre(elem: ET.Element) -> str:
    """Handle <m:sPre> → {}_{sub}^{sup}{e}."""
    e_val = _child_convert(elem, "e")
    sub = _child_convert(elem, "sub")
    sup = _child_convert(elem, "sup")
    parts: list[str] = []
    if sub:
        parts.append(f"_{{{sub}}}")
    if sup:
        parts.append(f"^{{{sup}}}")
    parts.append(_wrap_group(e_val))
    return "".join(parts)


# ── N-ary operators (sum, integral, product, etc.) ──


def _handle_nary(elem: ET.Element) -> str:
    """Handle <m:nary> → \\sum_{sub}^{sup} or \\int_{sub}^{sup}, etc."""
    # Read the operator character from <m:chr>
    chr_val = _child_attr(elem, "chr", "val")
    op = _NARY_OPERATOR_MAP.get(chr_val or "", r"\sum")

    sub = _child_convert(elem, "sub")
    sup = _child_convert(elem, "sup")
    e_val = _child_convert(elem, "e")

    # Build the limits
    limits = ""
    if sub:
        limits += f"_{{{sub}}}"
    if sup:
        limits += f"^{{{sup}}}"

    return f"{op}{limits} {{{e_val}}}"


# ── Accents ──


def _handle_acc(elem: ET.Element) -> str:
    """Handle <m:acc> → \\hat{e}, \\vec{e}, etc."""
    chr_val = _child_attr(elem, "chr", "val")
    cmd = _ACCENT_MAP.get(chr_val or "", r"\hat")
    e_val = _child_convert(elem, "e")
    return f"{cmd}{{{e_val}}}"


# ── Overline/underline ──


def _handle_bar(elem: ET.Element) -> str:
    """Handle <m:bar> → \\overline{e} or \\underline{e}."""
    pos = _child_attr(elem, "pr", "pos") or "top"
    e_val = _child_convert(elem, "e")
    if pos == "bot":
        return rf"\underline{{{e_val}}}"
    return rf"\overline{{{e_val}}}"


# ── Math functions ──


def _handle_func(elem: ET.Element) -> str:
    """Handle <m:func> → \\sin{e} or \\lim_{sub} e."""
    fname_text = _func_name(elem)
    func_cmd = _FUNC_MAP.get(fname_text, rf"\operatorname{{{fname_text}}}")

    # Check for limits (e.g. lim's subscript)
    lim = _child_convert(elem, "lim")
    e_val = _child_convert(elem, "e")

    result = func_cmd
    if lim:
        result += f"_{{{lim}}}"
    if e_val:
        result += f"{{{e_val}}}"
    return result


def _func_name(elem: ET.Element) -> str:
    """Extract the function name text from <m:fName>."""
    fname = first_child(elem, "m", "fName")
    if fname is None:
        return ""
    return _plain_text(fname).strip()


# ── Bracket groups ──


def _handle_groupchr(elem: ET.Element) -> str:
    """Handle <m:groupChr> → {e} or a bracket group with a symbol above."""
    chr_val = _child_attr(elem, "pr", "chr") or _child_attr(elem, "groupChrPr", "chr")
    e_val = _child_convert(elem, "e")
    if chr_val is not None:
        return rf"\overbrace{{{e_val}}}" if chr_val == "⏞" else f"{{{e_val}}}"
    return f"{{{e_val}}}"


# ── Delimiters (parentheses) ──


def _handle_d(elem: ET.Element) -> str:
    """Handle <m:d> → \\left( e \\right)."""
    beg_chr = _child_attr(elem, "pr", "begChr") or "("
    end_chr = _child_attr(elem, "pr", "endChr") or ")"
    beg = _DELIM_MAP.get(beg_chr, beg_chr)
    end = _DELIM_MAP.get(end_chr, end_chr)
    e_val = _child_convert(elem, "e")
    return rf"\left{beg} {e_val} \right{end}"


# ── Matrices ──


def _handle_m(elem: ET.Element) -> str:
    """Handle <m:m> (matrix) → \\begin{matrix}...\\end{matrix}."""
    rows: list[str] = []
    for mr in child_elements(elem, "m", "mr"):
        cells = [_convert_node(cell) for cell in mr if local_name(cell.tag) == "e"]
        rows.append(" & ".join(cells))
    body = r" \\ ".join(rows)
    return rf"\begin{{matrix}} {body} \end{{matrix}}"


# ── Equation arrays ──


def _handle_eqarr(elem: ET.Element) -> str:
    """Handle <m:eqArr> → \\begin{aligned}...\\end{aligned}."""
    rows = [_convert_node(child) for child in elem if local_name(child.tag) == "e"]
    body = r" \\ ".join(rows)
    return rf"\begin{{aligned}} {body} \end{{aligned}}"


# ── Limits ──


def _handle_limlow(elem: ET.Element) -> str:
    """Handle <m:limLow> → {e}_{lim}."""
    e_val = _child_convert(elem, "e")
    lim = _child_convert(elem, "lim")
    return f"{{{e_val}}}_{{{lim}}}"


def _handle_limupp(elem: ET.Element) -> str:
    """Handle <m:limUpp> → {e}^{lim}."""
    e_val = _child_convert(elem, "e")
    lim = _child_convert(elem, "lim")
    return f"{{{e_val}}}^{{{lim}}}"


# ── Phantom/border box/box ──


def _handle_phant(elem: ET.Element) -> str:
    """Handle <m:phant> → \\phantom{e}."""
    e_val = _child_convert(elem, "e")
    return rf"\phantom{{{e_val}}}"


def _handle_borderbox(elem: ET.Element) -> str:
    """Handle <m:borderBox> → \\boxed{e}."""
    e_val = _child_convert(elem, "e")
    return rf"\boxed{{{e_val}}}"


def _handle_box(elem: ET.Element) -> str:
    """Handle <m:box>: pass through child elements."""
    return _convert_children(elem)


# ── Helper functions ──


def _child_convert(elem: ET.Element, child_local: str) -> str:
    """Find the first child with the given local name and convert it; return "" when absent."""
    child = first_child(elem, "m", child_local)
    if child is None:
        return ""
    return _convert_node(child)


def _child_attr(elem: ET.Element, child_local: str, attr_name: str) -> str | None:
    """Read the attribute value of the specified child element."""
    child = first_child(elem, "m", child_local)
    if child is None:
        return None
    return attr(child, "m", attr_name)


def _convert_children(elem: ET.Element) -> str:
    """Convert all child elements and concatenate (LaTeX math mode ignores whitespace)."""
    parts: list[str] = []
    for child in elem:
        latex = _convert_node(child)
        if latex:
            parts.append(latex)
    return "".join(parts)


# ── Element dispatch table ──

_DISPATCH: dict[str, Callable[[ET.Element], str]] = {
    "r": _handle_r,
    "t": _handle_t,
    "f": _handle_f,
    "rad": _handle_rad,
    "sSub": _handle_ssub,
    "sSup": _handle_ssup,
    "sSubSup": _handle_ssubsup,
    "sPre": _handle_spre,
    "nary": _handle_nary,
    "acc": _handle_acc,
    "bar": _handle_bar,
    "func": _handle_func,
    "groupChr": _handle_groupchr,
    "d": _handle_d,
    "m": _handle_m,
    "eqArr": _handle_eqarr,
    "limLow": _handle_limlow,
    "limUpp": _handle_limupp,
    "phant": _handle_phant,
    "borderBox": _handle_borderbox,
    "box": _handle_box,
    # Container elements: pass through child elements
    "oMath": _convert_children,
    "oMathPara": _convert_children,
    # The elements below pass through their children directly
    "e": _convert_children,
    "num": _convert_children,
    "den": _convert_children,
    "sub": _convert_children,
    "sup": _convert_children,
    "deg": _convert_children,
    "lim": _convert_children,
    "fName": lambda e: _plain_text(e).strip(),
    "chr": lambda e: e.get(qualified_name("m", "val"), ""),
    # Formatting control elements: produce no output
    "oMathParaPr": lambda e: "",
    "oMathPr": lambda e: "",
    "sSubPr": lambda e: "",
    "sSupPr": lambda e: "",
    "sSubSupPr": lambda e: "",
    "sPrePr": lambda e: "",
    "fPr": lambda e: "",
    "naryPr": lambda e: "",
    "radPr": lambda e: "",
    "accPr": lambda e: "",
    "barPr": lambda e: "",
    "dPr": lambda e: "",
    "mPr": lambda e: "",
    "eqArrPr": lambda e: "",
    "groupChrPr": lambda e: "",
    "ctrlPr": lambda e: "",
    "rPr": lambda e: "",
    "sty": lambda e: "",
    "jc": lambda e: "",
}
