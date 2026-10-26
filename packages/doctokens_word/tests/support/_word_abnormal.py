"""Damaged/unsupported Word image setup shared by exception tests."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from _word_packages import _make_docx
from doctokens_word.docx.ooxml.namespaces import NS

from test_support.paths import REPO_ROOT

DECLARATIONS = f'xmlns:v="{NS["v"]}" xmlns:o="{NS["o"]}"'
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
PNG = REPO_ROOT / "test_support/fixture-assets/ff0000.png"


def _abnormal_docx(body: str, entries: dict[str, str], *, with_image: bool = True) -> bytes:
    entries = {"word/styles.xml": f'<w:styles xmlns:w="{NS["w"]}"/>', **entries}
    buffer = BytesIO(_make_docx(body, entries))
    if with_image:
        with ZipFile(buffer, "a") as archive:
            archive.writestr("word/media/valid.png", PNG.read_bytes())
    return buffer.getvalue()
