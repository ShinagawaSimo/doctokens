"""DrawingML text-body result and single-pass parser boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ....core.models import Paragraph, ParagraphStyle, Run

HyperlinkLookup = dict[tuple[str, str], str]
RunParser = Callable[
    [
        ET.Element | None,
        str,
        list[ParseWarning],
        dict[str, str],
        dict[str, str],
        HyperlinkLookup,
        dict[int, ParagraphStyle] | None,
        list[Paragraph] | None,
        bool,
    ],
    list[Run],
]


@dataclass(slots=True)
class TextBodyResult:
    """Single-pass text result for one DrawingML ``a:txBody`` subtree."""

    text: str | None
    runs: list[Run]
    paragraphs: list[Paragraph]


class DrawingTextParser:
    """Build text, run and paragraph IR through one injected run parser."""

    def __init__(
        self,
        warnings: list[ParseWarning],
        hyperlink_lookup: HyperlinkLookup,
        run_parser: RunParser,
        *,
        include_formatting: bool,
    ) -> None:
        self._warnings = warnings
        self._hyperlink_lookup = hyperlink_lookup
        self._run_parser = run_parser
        self._include_formatting = include_formatting

    def parse(
        self,
        tx_body: ET.Element | None,
        *,
        part: str,
        theme: dict[str, str],
        color_map: dict[str, str],
        inherited_styles: dict[int, ParagraphStyle] | None = None,
    ) -> TextBodyResult:
        paragraphs: list[Paragraph] = []
        runs = self._run_parser(
            tx_body,
            part,
            self._warnings,
            theme,
            color_map,
            self._hyperlink_lookup,
            inherited_styles,
            paragraphs,
            self._include_formatting,
        )
        text = "".join(run.get("text", "") for run in runs)
        return TextBodyResult(text or None, runs, paragraphs)


__all__ = ["DrawingTextParser", "HyperlinkLookup", "TextBodyResult"]
