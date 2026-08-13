"""PPTX package reader tests using a generated PPTX package."""

from __future__ import annotations

import unittest

from _pptx_fixtures import content_types_xml, make_pptx, presentation_xml, root_rels_xml
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.core.package import PackageError, PackageReader


def _valid_entries() -> dict[str, str]:
    return {
        "[Content_Types].xml": content_types_xml(),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(),
    }


class PptxPackageReaderTests(unittest.TestCase):
    def test_validate_accepts_presentation_package(self) -> None:
        with PackageReader(make_pptx(_valid_entries()), ParseOptions()) as pkg:
            pkg.validate()

    def test_validate_requires_presentation_part_by_default(self) -> None:
        entries = _valid_entries()
        entries.pop("ppt/presentation.xml")
        with (
            PackageReader(make_pptx(entries), ParseOptions()) as pkg,
            self.assertRaisesRegex(PackageError, "Missing ppt/presentation.xml"),
        ):
            pkg.validate()

    def test_validate_requires_content_types(self) -> None:
        entries = _valid_entries()
        entries.pop("[Content_Types].xml")
        with (
            PackageReader(make_pptx(entries), ParseOptions()) as pkg,
            self.assertRaisesRegex(PackageError, "Missing \\[Content_Types\\].xml"),
        ):
            pkg.validate()

    def test_read_entry_index_lists_members(self) -> None:
        with PackageReader(make_pptx(_valid_entries()), ParseOptions()) as pkg:
            names = {entry["name"] for entry in pkg.read_entry_index()}
        self.assertIn("ppt/presentation.xml", names)
        self.assertIn("[Content_Types].xml", names)

    def test_read_all_relationships_finds_office_document(self) -> None:
        with PackageReader(make_pptx(_valid_entries()), ParseOptions()) as pkg:
            records = pkg.read_all_relationships()
        office = [record for record in records if record.id == "rId1"]
        self.assertEqual(len(office), 1)
        self.assertEqual(office[0].target, "ppt/presentation.xml")
        self.assertEqual(office[0].resolved_target, "ppt/presentation.xml")

    def test_rejects_non_zip_source(self) -> None:
        with self.assertRaisesRegex(PackageError, "Not a valid zip"), PackageReader(b"not a zip", ParseOptions()):
            pass


if __name__ == "__main__":
    unittest.main()
