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

    def test_rejects_non_zip_source(self) -> None:
        with self.assertRaisesRegex(PackageError, "Not a valid zip"), PackageReader(b"not a zip", ParseOptions()):
            pass


if __name__ == "__main__":
    unittest.main()
