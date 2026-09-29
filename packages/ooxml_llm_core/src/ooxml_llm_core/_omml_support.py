"""omml support."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .xml import NS as _NS_OPC
from .xml import attr as _core_attr
from .xml import child_elements as _core_child_elements
from .xml import first_child as _core_first_child
from .xml import qualified_name as _core_qualified_name

NS = {**_NS_OPC, "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}


def qualified_name(prefix: str, local: str) -> str:
    return _core_qualified_name(prefix, local, NS)


def attr(el: ET.Element, prefix: str, local: str, default: str | None = None) -> str | None:
    return _core_attr(el, prefix, local, default, NS)


def first_child(el: ET.Element | None, prefix: str, local: str) -> ET.Element | None:
    return _core_first_child(el, prefix, local, NS)


def child_elements(el: ET.Element | None, prefix: str, local: str) -> list[ET.Element]:
    return _core_child_elements(el, prefix, local, NS)


# ── N-ary operator map ──
# <m:chr> Unicode character value → LaTeX command
_NARY_OPERATOR_MAP: dict[str, str] = {
    "∑": r"\sum",  # ∑
    "∏": r"\prod",  # ∏
    "∐": r"\coprod",  # ∐
    "∫": r"\int",  # ∫
    "∬": r"\iint",  # ∬
    "∭": r"\iiint",  # ∭
    "∮": r"\oint",  # ∮
    "⋃": r"\bigcup",  # ⋃
    "⋂": r"\bigcap",  # ⋂
    "⋀": r"\bigwedge",  # ⋀
    "⋁": r"\bigvee",  # ⋁
    "⨀": r"\bigodot",  # ⨀
    "⨁": r"\bigoplus",  # ⨁
    "⨂": r"\bigotimes",  # ⨂
}


# ── Accent map ──
# <m:acc> <m:chr> value → LaTeX accent command
_ACCENT_MAP: dict[str, str] = {
    "̂": r"\hat",  # circumflex  ̂
    "̃": r"\tilde",  # tilde  ̃
    "̇": r"\dot",  # dot      ̇
    "̈": r"\ddot",  # double dot    ̈
    "⃗": r"\vec",  # vector arrow ⃗
    "̄": r"\bar",  # overline  ̄
    "̆": r"\breve",  # breve  ̆
    "̌": r"\check",  # caron  ̌
    "̀": r"\grave",  # grave accent  ̀
    "́": r"\acute",  # acute accent  ́
}


# ── Math function map ──
# <m:func> <m:fName> text → LaTeX function command
_FUNC_MAP: dict[str, str] = {
    "sin": r"\sin",
    "cos": r"\cos",
    "tan": r"\tan",
    "csc": r"\csc",
    "sec": r"\sec",
    "cot": r"\cot",
    "sinh": r"\sinh",
    "cosh": r"\cosh",
    "tanh": r"\tanh",
    "arcsin": r"\arcsin",
    "arccos": r"\arccos",
    "arctan": r"\arctan",
    "log": r"\log",
    "ln": r"\ln",
    "lg": r"\lg",
    "exp": r"\exp",
    "max": r"\max",
    "min": r"\min",
    "sup": r"\sup",
    "inf": r"\inf",
    "lim": r"\lim",
    "limsup": r"\limsup",
    "liminf": r"\liminf",
    "det": r"\det",
    "gcd": r"\gcd",
    "deg": r"\deg",
    "dim": r"\dim",
    "hom": r"\hom",
    "ker": r"\ker",
    "arg": r"\arg",
    "mod": r"\mod",
    "Pr": r"\Pr",
}


# ── Bracket/delimiter map ──
# <m:dPr> begChr/endChr characters → LaTeX delimiters
_DELIM_MAP: dict[str, str] = {
    "(": "(",
    ")": ")",
    "[": "[",
    "]": "]",
    "{": r"\{",
    "}": r"\}",
    "|": "|",
    "‖": r"\|",  # ‖ double vertical bar
    "⌊": r"\lfloor",  # ⌊
    "⌋": r"\rfloor",  # ⌋
    "⌈": r"\lceil",  # ⌈
    "⌉": r"\rceil",  # ⌉
    "⟨": r"\langle",  # ⟨
    "⟩": r"\rangle",  # ⟩
}


def _wrap_group(latex: str) -> str:
    """Wrap LaTeX in braces when grouping is needed (fractions, radicals, multi-char content)."""
    if not latex:
        return "{}"
    if any(cmd in latex for cmd in (r"\frac", r"\sqrt", r"\sum", r"\int", r"\prod")):
        return f"{{{latex}}}"
    if " " in latex or len(latex) > 1:
        return f"{{{latex}}}"
    return latex


def _plain_text(elem: ET.Element) -> str:
    """Extract all <m:t> text within the element (used as a fallback)."""
    parts = [mt.text for mt in elem.iter(qualified_name("m", "t")) if mt.text]
    return "".join(parts)


def _escape_latex(text: str) -> str:
    """Escape LaTeX special characters."""
    # Escape order matters: backslash first, then braces
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for char, repl in replacements:
        text = text.replace(char, repl)
    return text
