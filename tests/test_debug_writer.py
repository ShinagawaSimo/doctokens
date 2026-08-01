from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from docx_llm_parser.core.debug import DebugWriter
from docx_llm_parser.core.models import ParseOptions


class DebugWriterTests(unittest.TestCase):
    def test_debug_is_disabled_by_default(self) -> None:
        self.assertFalse(ParseOptions().debug)

    def test_disabled_writer_does_not_create_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            debug_dir = Path(temporary_dir) / "debug"

            with DebugWriter(debug_dir, enabled=False) as writer:
                writer.write_json("ignored.json", {"value": 1})

            self.assertFalse(debug_dir.exists())

    def test_json_and_jsonl_are_written_without_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            debug_dir = Path(temporary_dir) / "debug"

            with DebugWriter(debug_dir) as writer:
                writer.write_json("value.json", {"name": "示例"})
                writer.write_jsonl("events.jsonl", [{"id": 1}, {"id": 2}])

            self.assertEqual(
                json.loads((debug_dir / "value.json").read_text("utf-8")), {"name": "示例"}
            )
            self.assertEqual(
                (debug_dir / "events.jsonl").read_text("utf-8").splitlines(),
                ['{"id": 1}', '{"id": 2}'],
            )
            self.assertEqual(list(debug_dir.glob("*.tmp")), [])

    def test_serialization_error_is_raised_and_partial_file_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            debug_dir = Path(temporary_dir) / "debug"
            writer = DebugWriter(debug_dir)

            with self.assertRaises(TypeError):
                writer.write_json("invalid.json", {"value": object()})

            self.assertFalse((debug_dir / "invalid.json").exists())
            self.assertEqual(list(debug_dir.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
