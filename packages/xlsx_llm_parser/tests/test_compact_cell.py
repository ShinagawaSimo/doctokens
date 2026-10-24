"""Storage-container contracts, independent of Office parsing/content policy."""

from __future__ import annotations

import copy
import pickle
import sys

import pytest
from xlsx_llm_parser.compact_cell import CompactCell


def test_mapping_mutation_and_views_match_dictionary_values() -> None:
    original = {"ref": "B3", "row": 3, "col": 2, "text": "", "style": 0, "raw": None}
    expected = dict(original)
    cell = CompactCell(original)
    assert original == expected
    assert dict(cell) == expected
    for key, value in (("formula", "A1"), ("text", "changed"), ("comment", "note"), ("raw", "0")):
        expected[key] = value
        cell[key] = value
    assert dict(cell.items()) == expected
    assert set(cell.keys()) == set(expected)
    for key in ("style", "formula", "comment", "text"):
        assert cell.pop(key) == expected.pop(key)
        assert key not in cell
        assert cell.get(key, "missing") == "missing"
        with pytest.raises(KeyError):
            _ = cell[key]
        with pytest.raises(KeyError):
            del cell[key]
    cell.update({"style": 1, "new": False})
    expected.update({"style": 1, "new": False})
    assert cell == expected
    assert len(cell) == len(expected)
    cell.clear()
    assert not cell and dict(cell) == {}


@pytest.mark.parametrize("duplicate", [copy.copy, copy.deepcopy, lambda cell: pickle.loads(pickle.dumps(cell))])
def test_copied_mapping_keeps_missing_fields_missing(duplicate) -> None:
    cell = CompactCell({"ref": "A1", "text": "value", "comment": "note"})
    result = duplicate(cell)
    assert dict(result) == dict(cell)
    assert "raw" not in result
    assert "style" not in result
    result["style"] = 0
    assert "style" not in cell


def test_common_fields_are_smaller_and_keep_shared_values() -> None:
    # Check the representation cost without constructing a synthetic workbook.
    text = "shared value"
    values = {"ref": "A1", "row": 1, "col": 1, "text": text, "raw": text, "type": "string", "style": 0}
    cell = CompactCell(values)
    assert not hasattr(cell, "__dict__")
    assert cell._extra is None
    assert sys.getsizeof(cell) < sys.getsizeof(values)
    assert cell["text"] is cell["raw"] is text
    rich = [{"text": text}]
    cell["rich"] = rich
    assert cell["rich"] is rich
