"""Shared helpers for file-backed parser tests."""

from .file_contract import (
    artifact_root,
    assert_json_matches_golden,
    assert_text_matches_golden,
    fixture_root,
    golden_root,
    materialize_bytes,
    output_path,
    source_path,
    write_text_result,
)

__all__ = [
    "artifact_root",
    "assert_json_matches_golden",
    "assert_text_matches_golden",
    "fixture_root",
    "golden_root",
    "materialize_bytes",
    "output_path",
    "source_path",
    "write_text_result",
]
