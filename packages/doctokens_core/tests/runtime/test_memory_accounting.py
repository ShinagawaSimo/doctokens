"""Reference-identity accounting and reservation failure contracts."""

import pytest
from doctokens_core.containers.opc.memory import SessionMemoryBudget
from doctokens_core.runtime.memory import ParseMemoryLimitError


def test_fragment_measurement_counts_local_shared_references_once() -> None:
    # Infrastructure identity accounting: this does not define parsing content.
    from doctokens_core.runtime.memory import object_bytes

    value = "a" * 1000
    assert object_bytes([value, value]) < object_bytes([value, value.encode().decode()])
    budget = SessionMemoryBudget(1024 * 1024 + 100)
    with pytest.raises(ParseMemoryLimitError):
        budget.add_fragment(value)
