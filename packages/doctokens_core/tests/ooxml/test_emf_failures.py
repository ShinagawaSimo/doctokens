"""EMF corruption, unsupported encodings and resource limits cannot be saved through ordinary Office text editing."""

from __future__ import annotations

import struct
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from doctokens_core.containers.opc.limits import PackageLimits
from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.ooxml.emf import MAX_CHARACTERS, MAX_RECORDS
from doctokens_core.output.image_text import image_text_resource


def _emf(*records: bytes) -> bytes:
    eof = struct.pack("<IIIII", 14, 20, 0, 0, 20)
    header = bytearray(88)
    struct.pack_into("<II", header, 0, 1, 88)
    header[40:44] = b" EMF"
    struct.pack_into("<III", header, 44, 0x10000, 88 + sum(map(len, records)) + 20, len(records) + 2)
    return bytes(header) + b"".join(records) + eof


def _text_record(data: bytes, *, options: int = 0, unicode: bool = True) -> bytes:
    length = (76 + len(data) + 3) & ~3
    record = bytearray(length)
    struct.pack_into("<II", record, 0, 84 if unicode else 83, length)
    struct.pack_into("<III", record, 44, len(data) // (2 if unicode else 1), 76, options)
    record[76 : 76 + len(data)] = data
    return bytes(record)


def _resource(data: bytes) -> str:
    carrier = BytesIO()
    with ZipFile(carrier, "w") as archive:
        archive.writestr("preview.emf", data)
    with PackageReader(carrier.getvalue(), PackageLimits(10, 50 * 1024 * 1024, 50 * 1024 * 1024)) as package:
        return image_text_resource(package, "preview.emf", "img1", "pptx")


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"", "invalid-emf-header"),
        (b"not emf data", "unsupported-image-format"),
        (_emf(struct.pack("<II", 84, 0xFFFFFFFC)), "invalid-record-size"),
        (_emf(_text_record(b"\x00\xd8")), "invalid-text-encoding"),
        (_emf(_text_record(b"\x01\x00", options=0x10)), "glyph-indices"),
        (_emf(_text_record(b"A", unicode=False)), "unresolved-codepage"),
    ],
)
def test_unreadable_saved_text_has_a_visible_placeholder(data: bytes, reason: str) -> None:
    output = _resource(data)
    root = ET.fromstring(output)
    assert root.find(".//image-text").get("partial") == "true"
    assert reason in [node.get("code") for node in root.findall(".//limitation")]
    assert root.find(".//unsupported") is not None
    assert not root.findall(".//text")


def test_text_record_offset_is_checked_against_its_own_record() -> None:
    record = bytearray(_text_record(b"A\0"))
    struct.pack_into("<I", record, 48, 0xFFFFFFFE)
    root = ET.fromstring(_resource(_emf(bytes(record))))
    assert [node.get("code") for node in root.findall(".//limitation")] == ["invalid-text-record"]
    assert root.find(".//unsupported").get("reason") == "invalid-text-record"


def test_character_cap_includes_xml_markup_and_escaping() -> None:
    # Repeated escaped characters can multiply serialized output size. This
    # exercises the fixed transport/decoder cap rather than normal text content.
    output = _resource(_emf(_text_record(("&" * (MAX_CHARACTERS + 1)).encode("utf-16-le"))))
    root = ET.fromstring(output)
    assert len(output) <= MAX_CHARACTERS
    assert root.find(".//image-text").get("partial") == "true"
    assert root.find(".//text").text
    assert "character-limit" in [node.get("code") for node in root.findall(".//limitation")]


def test_record_cap_stops_a_very_long_drawing_sequence() -> None:
    # A huge synthetic GDI sequence is necessary to hit the parser's record cap
    # deterministically without authoring 100000 Office drawing operations.
    output = _resource(_emf(struct.pack("<II", 33, 8) * MAX_RECORDS))
    root = ET.fromstring(output)
    assert "record-limit" in [node.get("code") for node in root.findall(".//limitation")]
    assert len(output) <= MAX_CHARACTERS
