"""Invalid table query parameters are infrastructure, independent of content goldens."""

from __future__ import annotations

import pytest
from doctokens_word.docx.rendering.objects.resources import _aggregate_rows, _numeric_column_values, _slice_rows


@pytest.mark.parametrize("value", ["5-3", "0-2", "bad", "1-0", "1-X"])
def test_invalid_row_range_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid rows range"):
        _slice_rows([], value)


def test_unknown_aggregate_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown aggregate"):
        _aggregate_rows([], "median", "Value")


def test_unknown_column_is_rejected() -> None:
    with pytest.raises(ValueError, match="not found"):
        _numeric_column_values([{"rowIndex": 0, "cells": []}], "Missing")
