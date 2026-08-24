"""Renderer metrics smoke tests for the explicit output contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx_llm_parser.core.models import ParsedDocument
from docx_llm_parser.renderers.common.metrics import record_render_metrics, write_metrics_debug


class RenderMetricsTests(unittest.TestCase):
    def test_record_and_write_metrics(self) -> None:
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
                debug_dir=str(root),
            )
            record_render_metrics(parsed, output, 4, 1.25)
            self.assertEqual(parsed.metrics["counters"]["outputChars"], 4)
            self.assertEqual(parsed.metrics["counters"]["outputBytes"], 4)
            write_metrics_debug(parsed)
            self.assertTrue((root / "metrics.json").is_file())

    def test_write_metrics_without_debug_dir_is_noop(self) -> None:
        parsed = ParsedDocument(metadata={}, package_info={}, blocks=[], relationships=[], styles=[], warnings=[])
        write_metrics_debug(parsed)


if __name__ == "__main__":
    unittest.main()
