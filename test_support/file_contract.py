"""Shared test-only file contract for OOXML parser integration tests.

Production parsers return text or iterators. This module owns test-side input
and output materialization, including the atomic write used for human-readable
artifacts and standalone golden comparisons.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile

_ARTIFACTS_ENV = "OOXML_TEST_ARTIFACTS"
_UPDATE_GOLDEN_ENV = "UPDATE_GOLDEN"


def artifact_root() -> Path:
    """Return the persistent root used for human-readable test artifacts."""

    configured = os.environ.get(_ARTIFACTS_ENV)
    root = Path(configured) if configured else Path("out") / "test-artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def materialize_bytes(
    data: bytes,
    *,
    suffix: str,
    package: str,
    name: str | None = None,
) -> Path:
    """Atomically write generated package bytes and return a real ``Path``.

    A content digest keeps repeated calls deterministic and prevents one test
    case from overwriting another case's input. ``name`` is a human-readable
    prefix; the digest remains part of the filename because several tests
    intentionally generate multiple variants of one format.
    """

    if not suffix.startswith("."):
        raise ValueError("suffix must start with '.'")
    digest = hashlib.sha256(data).hexdigest()[:12]
    prefix = _safe_name(name or "fixture")
    target = artifact_root() / "inputs" / _safe_name(package) / f"{prefix}-{digest}{suffix}"
    _atomic_write_bytes(target, data)
    return target


def output_path(package: str, case: str, filename: str) -> Path:
    """Return and create a stable output path for one integration case."""

    target = artifact_root() / "outputs" / _safe_name(package) / _safe_name(case) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def source_path(package: str, case: str, filename: str) -> Path:
    """Return and create a stable source path for a file-backed test case."""

    target = artifact_root() / "inputs" / _safe_name(package) / _safe_name(case) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def fixture_root(package: str | None = None) -> Path:
    """Return the checked-in root for manually authored Office fixtures."""

    root = Path(__file__).resolve().parent / "fixtures"
    if package:
        root /= _safe_name(package)
    return root


def golden_root(package: str | None = None) -> Path:
    """Return the checked-in root for standalone golden output files."""

    root = Path(__file__).resolve().parent / "golden"
    if package:
        root /= _safe_name(package)
    return root


def write_text_result(result: object, target: Path) -> Path:
    """Write a complete or streaming renderer result as UTF-8 text."""

    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        try:
            text = getattr(result, "text", result)
            if isinstance(text, str):
                stream.write(text)
            elif isinstance(text, Iterable):
                for chunk in text:
                    stream.write(chunk)
            else:
                raise TypeError("result must be text, an iterable of text chunks, or expose .text")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(target)
    return target


def assert_text_matches_golden(actual: Path, golden: Path) -> None:
    """Compare output and golden files byte for byte."""

    actual_bytes = actual.read_bytes()
    if os.environ.get(_UPDATE_GOLDEN_ENV):
        _atomic_write_bytes(golden, actual_bytes)
    if not golden.exists():
        raise AssertionError(f"golden file does not exist: {golden}")
    expected_bytes = golden.read_bytes()
    if actual_bytes != expected_bytes:
        actual_text = actual_bytes.decode("utf-8", errors="replace")
        expected_text = expected_bytes.decode("utf-8", errors="replace")
        raise AssertionError(
            f"output differs from golden: {actual}\n"
            f"golden: {golden}\n"
            f"actual length={len(actual_text)}, expected length={len(expected_text)}\n"
            f"actual={actual_text!r}\nexpected={expected_text!r}"
        )


def assert_json_matches_golden(actual: Path, golden: Path, *, exclude: set[str] | None = None) -> None:
    """Compare JSON artifacts after stable key ordering and formatting."""

    excluded = exclude or set()
    if actual.name in excluded:
        return
    normalized = json.dumps(json.loads(actual.read_text(encoding="utf-8")), ensure_ascii=False, sort_keys=True)
    if os.environ.get(_UPDATE_GOLDEN_ENV):
        _atomic_write_text(golden, normalized)
    if not golden.exists():
        raise AssertionError(f"golden file does not exist: {golden}")
    expected = golden.read_text(encoding="utf-8")
    if expected != normalized:
        raise AssertionError(f"JSON artifact differs from golden: {actual}\ngolden: {golden}")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "case"


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="wb", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(target)


def _atomic_write_text(target: Path, text: str) -> None:
    _atomic_write_bytes(target, text.encode("utf-8"))


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
