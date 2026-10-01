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
    def test_get_returns_none_on_miss(self) -> None:
        idx = RelationshipIndex.from_records([_rec("doc", "rId1", "image")])
        self.assertIsNone(idx.get("doc", "rId99"))

    def test_require_raises_keyerror_on_miss(self) -> None:
        idx = RelationshipIndex.from_records([])
        with self.assertRaises(KeyError):
            idx.require("doc", "rId99")

    def test_by_source_absent_returns_empty_tuple(self) -> None:
        idx = RelationshipIndex.from_records([])
        self.assertEqual(idx.by_source("absent"), ())

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
