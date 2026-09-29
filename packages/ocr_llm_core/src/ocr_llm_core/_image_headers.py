"""image headers."""

from __future__ import annotations

from typing import Literal


def _image_suffix(image_bytes: bytes) -> str | None:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if image_bytes.startswith(b"BM"):
        return "bmp"
    if image_bytes.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    return None


def _image_dimensions(image_bytes: bytes, suffix: str) -> tuple[int, int] | None:
    """Read dimensions from common image headers without adding a cloud-adapter dependency."""
    if suffix == "png":
        if len(image_bytes) >= 24 and image_bytes[12:16] == b"IHDR":
            return (int.from_bytes(image_bytes[16:20], "big"), int.from_bytes(image_bytes[20:24], "big"))
        return None
    if suffix == "jpg":
        return _jpeg_dimensions(image_bytes)
    if suffix == "bmp":
        if len(image_bytes) < 26:
            return None
        dib_size = int.from_bytes(image_bytes[14:18], "little")
        if dib_size == 12:
            return (int.from_bytes(image_bytes[18:20], "little"), int.from_bytes(image_bytes[20:22], "little"))
        width = int.from_bytes(image_bytes[18:22], "little", signed=True)
        height = int.from_bytes(image_bytes[22:26], "little", signed=True)
        return (abs(width), abs(height))
    if suffix == "tiff":
        return _tiff_dimensions(image_bytes)
    return None


def _jpeg_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    position = 2
    start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while position < len(image_bytes):
        if image_bytes[position] != 0xFF:
            position += 1
            continue
        while position < len(image_bytes) and image_bytes[position] == 0xFF:
            position += 1
        if position >= len(image_bytes):
            return None
        marker = image_bytes[position]
        position += 1
        if marker in {0x00, 0x01, *range(0xD0, 0xD9)}:
            continue
        if marker in {0xD9, 0xDA} or position + 2 > len(image_bytes):
            return None
        segment_length = int.from_bytes(image_bytes[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(image_bytes):
            return None
        if marker in start_of_frame and segment_length >= 7:
            height = int.from_bytes(image_bytes[position + 3 : position + 5], "big")
            width = int.from_bytes(image_bytes[position + 5 : position + 7], "big")
            return (width, height)
        position += segment_length
    return None


def _tiff_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    if len(image_bytes) < 8:
        return None
    byte_order: Literal["little", "big"] = "little" if image_bytes.startswith(b"II*\x00") else "big"
    ifd_offset = int.from_bytes(image_bytes[4:8], byte_order)
    if ifd_offset + 2 > len(image_bytes):
        return None
    entry_count = int.from_bytes(image_bytes[ifd_offset : ifd_offset + 2], byte_order)
    if entry_count > 4096:
        return None
    dimensions: dict[int, int] = {}
    for index in range(entry_count):
        start = ifd_offset + 2 + index * 12
        if start + 12 > len(image_bytes):
            return None
        tag = int.from_bytes(image_bytes[start : start + 2], byte_order)
        if tag not in (256, 257):
            continue
        field_type = int.from_bytes(image_bytes[start + 2 : start + 4], byte_order)
        count = int.from_bytes(image_bytes[start + 4 : start + 8], byte_order)
        if count < 1:
            continue
        if field_type == 3 and count == 1:
            value = int.from_bytes(image_bytes[start + 8 : start + 10], byte_order)
        elif field_type == 4 and count == 1:
            value = int.from_bytes(image_bytes[start + 8 : start + 12], byte_order)
        else:
            continue
        dimensions[tag] = value
    if 256 in dimensions and 257 in dimensions:
        return (dimensions[256], dimensions[257])
    return None
