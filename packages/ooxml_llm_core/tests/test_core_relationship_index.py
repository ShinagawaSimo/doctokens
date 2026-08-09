"""Characterization tests for RelationshipIndex."""

import unittest

from ooxml_llm_core.models import RelationshipRecord
from ooxml_llm_core.relationships import RelationshipIndex


def _rec(source: str, rel_id: str, rel_type: str, **kwargs: str | None) -> RelationshipRecord:
    return RelationshipRecord(
        source_part=source,
        id=rel_id,
        type=f"http://schemas.openxmlformats.org/officeDocument/2006/relationships/{rel_type}",
        target=str(kwargs.pop("target", f"{rel_type}/target")),
        target_mode=kwargs.pop("target_mode", None),
        resolved_target=str(kwargs.pop("resolved_target", f"resolved/{rel_type}")),
    )


class RelationshipIndexTests(unittest.TestCase):
    def test_get_returns_record_on_hit(self) -> None:
        idx = RelationshipIndex.from_records([_rec("doc", "rId1", "image"), _rec("doc", "rId2", "chart")])
        self.assertIsNotNone(idx.get("doc", "rId1"))
        result = idx.get("doc", "rId1")
        assert result is not None
        self.assertEqual(result.id, "rId1")

    def test_get_returns_none_on_miss(self) -> None:
        idx = RelationshipIndex.from_records([_rec("doc", "rId1", "image")])
        self.assertIsNone(idx.get("doc", "rId99"))

    def test_require_returns_record_on_hit(self) -> None:
        idx = RelationshipIndex.from_records([_rec("doc", "rId1", "image")])
        self.assertEqual(idx.require("doc", "rId1").id, "rId1")

    def test_require_raises_keyerror_on_miss(self) -> None:
        idx = RelationshipIndex.from_records([])
        with self.assertRaises(KeyError):
            idx.require("doc", "rId99")

    def test_by_source_returns_tuple(self) -> None:
        idx = RelationshipIndex.from_records([_rec("doc", "r1", "image"), _rec("doc", "r2", "chart")])
        result = idx.by_source("doc")
        self.assertEqual(len(result), 2)

    def test_by_source_absent_returns_empty_tuple(self) -> None:
        idx = RelationshipIndex.from_records([])
        self.assertEqual(idx.by_source("absent"), ())

    def test_by_type_without_filter(self) -> None:
        idx = RelationshipIndex.from_records(
            [
                _rec("doc", "r1", "image"),
                _rec("sheet", "r2", "image"),
                _rec("doc", "r3", "chart"),
            ]
        )
        images = idx.by_type("http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
        self.assertEqual(len(images), 2)

    def test_by_type_with_source_filter(self) -> None:
        idx = RelationshipIndex.from_records([_rec("doc", "r1", "image"), _rec("sheet", "r2", "image")])
        images = idx.by_type(
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
            source_part="doc",
        )
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].id, "r1")

    def test_to_debug_list(self) -> None:
        idx = RelationshipIndex.from_records([_rec("doc", "r1", "image")])
        debug = idx.to_debug_list()
        self.assertEqual(len(debug), 1)
        self.assertEqual(debug[0]["id"], "r1")

    def test_duplicate_rId_last_wins(self) -> None:
        idx = RelationshipIndex.from_records(
            [
                _rec("doc", "r1", "image", target="first"),
                _rec("doc", "r1", "chart", target="second"),
            ]
        )
        self.assertEqual(idx.require("doc", "r1").type.split("/")[-1], "chart")

    def test_from_records_empty_is_valid(self) -> None:
        idx = RelationshipIndex.from_records([])
        self.assertEqual(idx.by_source("any"), ())
        self.assertEqual(idx.to_debug_list(), [])
