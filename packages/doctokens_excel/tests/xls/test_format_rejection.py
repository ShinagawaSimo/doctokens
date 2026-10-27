"""Malformed BIFF formatting cannot be saved as ordinary Office documents."""

import pytest
from doctokens_excel.xls.formats import read_number_format, read_xf
from doctokens_excel.xls.models import XlsError, XlsLimits


@pytest.mark.parametrize(
    "data",
    [
        b"",
        bytes(4),
        b"\xa4\x00\x00\x00\x00",  # Zero-character format strings are forbidden.
        b"\x00\x00\x01\x00\x00x",  # Format cannot redefine General (identifier 0).
        b"\xa4\x00\x00\x01\x00",  # 256 UTF-16 units exceed the Format limit.
        b"\xa4\x00\x01\x00\x01x",  # Truncated double-byte character.
        b"\xa4\x00\x01\x00\x00xy",  # Unclaimed trailing data.
        b"\xa4\x00\x01\x00\x01\x00\xd8",  # Unpaired UTF-16 surrogate.
    ],
)
def test_invalid_format_records_are_rejected(data: bytes) -> None:
    with pytest.raises(XlsError):
        read_number_format(data)


@pytest.mark.parametrize("data", [bytes(19), bytes(21), b"\x00\x00\xff\xff" + bytes(16)])
def test_invalid_xf_records_are_rejected(data: bytes) -> None:
    with pytest.raises(XlsError):
        read_xf(data)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_xf_budget_must_be_a_positive_integer(value: object) -> None:
    with pytest.raises(ValueError, match="max_xfs"):
        XlsLimits(max_xfs=value)
