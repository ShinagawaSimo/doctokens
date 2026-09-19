"""Renderer metrics smoke tests for the explicit output contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx_llm_parser.core.models import ParsedDocument
from docx_llm_parser.rendering.common.metrics import record_render_metrics


class RenderMetricsTests(unittest.TestCase):
    def test_record_metrics_in_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "parsed.html"
            output.write_text("abcd", encoding="utf-8")
            parsed = ParsedDocument(
                metadata={},
                package_info={},
                blocks=[],
                relationships=[],
                styles=[],
                warnings=[],
            )
            record_render_metrics(parsed, output, 4, 1.25)
            self.assertEqual(parsed.metrics["counters"]["outputChars"], 4)
            self.assertEqual(parsed.metrics["counters"]["outputBytes"], 4)


if __name__ == "__main__":
    unittest.main()
