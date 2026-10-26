"""Exceptional inputs only; normal CFB behavior requires real Office files."""

import pytest
from doctokens_core.containers.cfb import CfbError, CfbLimits, CfbReader


@pytest.mark.parametrize("data", [b"", b"not an Office file", b"PK\x03\x04" + bytes(508), bytes(512)])
def test_non_cfb_or_truncated_input_is_rejected(data: bytes) -> None:
    # Wrong formats and truncated headers cannot be saved as valid Office files.
    reader = CfbReader(data)
    with pytest.raises(CfbError), reader:
        pytest.fail("Invalid input must not open")
    reader.close()
    with pytest.raises(RuntimeError, match="not open"):
        reader.open_root_stream("Workbook")


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_cfb_limit_validation_precedes_allocation(value: object) -> None:
    with pytest.raises(ValueError, match="max_file_bytes"):
        CfbLimits(max_file_bytes=value)
