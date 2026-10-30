"""Broken parent graphs cannot be saved through ordinary Office reply controls."""

from __future__ import annotations

import pytest
from doctokens_core.contracts.annotations import valid_parent_links


@pytest.mark.parametrize(
    ("rows", "expected", "invalid"),
    [
        ([("a", "missing")], {}, {"missing"}),
        ([("a", "a")], {}, {"a"}),
        ([("a", "b"), ("b", "a"), ("reply", "a")], {"reply": "a"}, {"a", "b"}),
        ([("a", "b"), ("b", "c"), ("c", "a")], {}, {"a", "b", "c"}),
    ],
)
def test_invalid_annotation_parent_graphs(rows, expected, invalid) -> None:
    assert valid_parent_links(rows) == (expected, invalid)
