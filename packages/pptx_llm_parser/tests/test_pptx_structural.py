"""Structural density rendering: exact output contract."""

from __future__ import annotations

import unittest

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, parse_pptx


class StructuralRenderingTests(unittest.TestCase):
    def test_structural_output_contract(self) -> None:
        text = parse_pptx(rich_deck_pptx(), density=Density.STRUCTURAL)
        self.assertEqual(
            text,
            "density=structural\n"
            "<slide n=1>\n"
            "<title>Title\n"
            "<p>Visit <a href=https://example.test/doc>docs</a>\n"
            '<img id=img1 alt="Chart photo">\n'
            "<table id=s4 rows=2 cols=2>\n"
            "<tr><td>A</td><td>B</td>\n"
            "<tr><td>C</td><td>D</td>\n"
            "<chart id=chart1 type=bar series=2 points=4 truncated>\n"
            "<smartart id=smartart1 type=process nodes=3 links=2 truncated>Start Middle End\n"
            "<media id=media1 kind=video>\n"
            "<notes>Talk\n"
            "<slide n=2 hidden>\n"
            "<p>Secret\n"
            "<!-- supplemental -->\n"
            "<comment id=cmt1 author=Alice date=2026-08-13T10:00:00>Nice slide\n"
            "<comment id=cmt2 author=Bob date=2026-08-13T11:00:00 parent=1>Agreed\n",
        )


if __name__ == "__main__":
    unittest.main()
