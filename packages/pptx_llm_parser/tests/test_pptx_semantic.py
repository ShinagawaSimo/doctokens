"""Semantic density rendering: exact output contract with coordinates and inline formats."""

from __future__ import annotations

import unittest

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, parse_pptx


class SemanticRenderingTests(unittest.TestCase):
    def test_semantic_output_contract(self) -> None:
        text = parse_pptx(rich_deck_pptx(with_geometry=True), density=Density.SEMANTIC)
        self.assertEqual(
            text,
            "density=semantic\n"
            "<slide n=1>\n"
            '<title id=s1 ph=title x=0 y=100 w=100 h=50 z=1 name="Title 1">Title\n'
            '<p id=s2 x=0 y=500 w=200 h=100 z=2 name="Body 2">Visit <a href=https://example.test/doc>docs</a>\n'
            '<img id=img1 alt="Chart photo" x=0 y=800 w=100 h=100 z=3 name="Picture 3">\n'
            '<table id=s4 rows=2 cols=2 z=4 name="Table 3">\n'
            "<tr><td>A</td><td>B</td>\n"
            "<tr><td>C</td><td>D</td>\n"
            '<chart id=chart1 type=bar series=2 points=4 truncated z=5 name="Chart 7">\n'
            '<smartart id=smartart1 type=process nodes=3 links=2 truncated z=6 name="Diagram 8">'
            "Start Middle End\n"
            '<media id=media1 kind=video z=7 name="Video 9">\n'
            "<notes>Talk\n"
            "<slide n=2 hidden>\n"
            '<p id=s1 z=1 name="Secret 2"><b><color value=#FF0000>Secret</color></b>\n'
            "<!-- supplemental -->\n"
            "<comment id=cmt1 author=Alice date=2026-08-13T10:00:00>Nice slide\n"
            "<comment id=cmt2 author=Bob date=2026-08-13T11:00:00 parent=1>Agreed\n",
        )


if __name__ == "__main__":
    unittest.main()
