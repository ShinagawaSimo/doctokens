"""Convert native Office mathematical structure to LaTeX reading expressions."""

from __future__ import annotations

import re
from collections.abc import Callable
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.xml import local_name

from . import operators, structures
from .results import MathResult, RevisionCollector, RevisionKind, RevisionView
from .support import _FUNC_MAP, _escape_latex, _plain_text, _wrap_group, attr, child_elements, first_child
from .text import HARD_BREAK, WarningSink, run_text, word_character

_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_SCRIPTS = frozenset(("limLow", "limUpp", "sSub", "sSup", "sSubSup", "sPre"))
_ARGUMENTS = frozenset(("e", "num", "den", "sub", "sup", "deg", "lim"))
_WRAPPERS = frozenset(("hyperlink", "fldSimple", "smartTag", "customXml", "sdtContent"))
_MARKERS = frozenset(("bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd", "commentRangeStart", "commentRangeEnd"))
_BARE_FUNCTION = re.compile(r"(?:\\[A-Za-z]+|\\operatorname\{[^{}]*\})")


def convert_math(elem: ET.Element, *, revision_mode: RevisionView = "final", warn: WarningSink | None = None) -> MathResult:
    """Return math text and review ranges with fresh, explicit per-call state."""
    if revision_mode not in {"final", "original", "review"}:
        raise ValueError(f"Invalid mathematical revision view: {revision_mode}")
    return _MathConverter(revision_mode, warn).convert(elem)


class _MathConverter:
    def __init__(self, view: RevisionView, warn: WarningSink | None) -> None:
        self.view = view
        self._warn = warn
        self._revisions = RevisionCollector()
        self._alignment: int | None = None
        self._handlers: dict[str, Callable[[ET.Element], str]] = {
            "r": self._run,
            "t": lambda node: self._escape_math(node.text or ""),
            "f": lambda node: structures.fraction(node, self.node),
            "rad": lambda node: structures.radical(node, self.node),
            "phant": lambda node: structures.phantom(node, self.node),
            "borderBox": lambda node: structures.border_box(node, self.node),
            "nary": lambda node: operators.nary(node, self.node),
            "acc": lambda node: operators.accent(node, self.node),
            "bar": lambda node: operators.bar(node, self.node),
            "d": lambda node: operators.delimiter(node, self.node),
            "groupChr": lambda node: operators.group_character(node, self.node),
            "m": self._matrix,
            "eqArr": self._array,
            "func": self._function,
            "fName": self._function_name,
            "oMath": self.children,
            "oMathPara": self._paragraph,
            "box": self.children,
        }

    def warn(self, code: str, message: str) -> None:
        if self._warn is not None:
            self._warn(code, message)

    def convert(self, elem: ET.Element) -> MathResult:
        return self._revisions.finish(self._lines(self.node(elem)))

    def node(self, node: ET.Element) -> str:
        name = local_name(node.tag)
        if node.tag.startswith(_W):
            return self._word(node, name)
        if not node.tag.startswith(_M):
            self.warn("MATH_CONTENT_UNSUPPORTED", f"Unsupported mathematical namespace: {node.tag}")
            return _escape_latex(_plain_text(node))
        if name.endswith("Pr") or name in {"sty", "jc"}:
            return ""
        if name in _ARGUMENTS:
            return self.children(node)
        if name in _SCRIPTS:
            if name in {"limLow", "limUpp"}:
                base = structures.argument(node, "e", self.node)
                limit = structures.argument(node, "lim", self.node)
                return f"{{{base}}}{'^' if name == 'limUpp' else '_'}{{{limit}}}"
            return structures.script(node, name, self.node)
        handler = self._handlers.get(name)
        if handler is not None:
            return handler(node)
        self.warn("MATH_CONTENT_UNSUPPORTED", f"Unsupported mathematical element: {name}")
        return _escape_latex(_plain_text(node))

    def children(self, elem: ET.Element) -> str:
        return self._lines("".join(self.node(child) for child in elem))

    @staticmethod
    def _lines(value: str) -> str:
        if HARD_BREAK not in value:
            return value
        return r"\begin{gathered} " + r" \\ ".join(value.split(HARD_BREAK)) + r" \end{gathered}"

    def _escape_math(self, value: str) -> str:
        if self._alignment is None or "&" not in value:
            return _escape_latex(value)
        parts: list[str] = []
        for char in value:
            if char == "&":
                self._alignment += 1
                # Odd markers align; even markers are adjustable source spacing.
                parts.append("&" if self._alignment % 2 else "")
            else:
                parts.append(_escape_latex(char))
        return "".join(parts)

    def _run(self, node: ET.Element) -> str:
        return run_text(node, self._escape_math, self.warn, alignment=self._alignment is not None)

    def _word(self, node: ET.Element, name: str, reader: Callable[[ET.Element], str] | None = None) -> str:
        read = reader or self.children
        if name in {"ins", "moveTo", "del", "moveFrom"}:
            inserted = name in {"ins", "moveTo"}
            if (inserted and self.view == "original") or (not inserted and self.view == "final"):
                return ""
            value = read(node)
            if self.view != "review":
                return value
            kind: RevisionKind = "inserted" if inserted else "deleted"
            return self._revisions.wrap(value, kind, attr(node, "w", "author"), attr(node, "w", "date"))
        if name in _WRAPPERS:
            return read(node)
        if name == "sdt":
            content = first_child(node, "w", "sdtContent")
            return read(content) if content is not None else ""
        if name == "r":
            return self._run(node)
        if name in {"t", "delText"}:
            return self._escape_math(node.text or "")
        if name in _MARKERS or name.endswith("Pr"):
            return ""
        return word_character(node, self.warn)

    def _paragraph(self, elem: ET.Element) -> str:
        values = [value for child in elem if child.tag == _M + "oMath" for value in [self.node(child)] if value]
        if len(values) < 2:
            return "".join(values)
        return r"\begin{gathered} " + r" \\ ".join(values) + r" \end{gathered}"

    def _matrix(self, elem: ET.Element) -> str:
        rows = [" & ".join(self.node(cell) for cell in child_elements(row, "m", "e")) for row in child_elements(elem, "m", "mr")]
        return r"\begin{matrix} " + r" \\ ".join(rows) + r" \end{matrix}"

    def _array(self, elem: ET.Element) -> str:
        rows: list[str] = []
        previous = self._alignment
        try:
            for row in child_elements(elem, "m", "e"):
                self._alignment = 0
                rows.append(self.node(row))
        finally:
            self._alignment = previous
        return r"\begin{aligned} " + r" \\ ".join(rows) + r" \end{aligned}"

    def _function(self, elem: ET.Element) -> str:
        name = first_child(elem, "m", "fName")
        value = self._function_name(name) if name is not None else ""
        if argument := structures.argument(elem, "e", self.node):
            value += f"{{{argument}}}"
        return value

    def _function_name(self, elem: ET.Element) -> str:
        name = local_name(elem.tag)
        if elem.tag.startswith(_W):
            return self._word(elem, name, self._function_contents)
        if name in _SCRIPTS:
            base = first_child(elem, "m", "e")
            value = self._function_name(base) if base is not None else ""
            if not _BARE_FUNCTION.fullmatch(value):
                value = _wrap_group(value)
            prefix = "{}" if name == "sPre" else value
            for part, marker in (("lim", "^" if name == "limUpp" else "_"), ("sub", "_"), ("sup", "^")):
                if argument := structures.argument(elem, part, self.node):
                    prefix += f"{marker}{{{argument}}}"
            return prefix + value if name == "sPre" else prefix
        return self._function_contents(elem)

    def _function_contents(self, elem: ET.Element) -> str:
        children = [child for child in elem if not local_name(child.tag).endswith("Pr")]
        if all(child.tag == _M + "r" and first_child(child, "m", "rPr") is None for child in children):
            text = _plain_text(elem).strip()
            return _FUNC_MAP.get(text, rf"\operatorname{{{_escape_latex(text)}}}") if text else ""
        return "".join(
            self._function_name(child) if local_name(child.tag) in _SCRIPTS or child.tag.startswith(_W) else self.node(child)
            for child in children
        )
