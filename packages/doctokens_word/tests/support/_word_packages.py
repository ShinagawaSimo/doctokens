"""Existing temporary Word package setup for pending native cases and exceptions."""

from __future__ import annotations

import io
import zipfile

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_docx(body_xml: str, extra_entries: dict[str, str] | None = None) -> bytes:
    """Build synthetic DOCX bytes whose body contains *body_xml*."""
    entries: dict[str, str] = {
        "[Content_Types].xml": (
            f'<Types xmlns="{NS_CT}">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'<Relationships xmlns="{NS_PKG_REL}">'
            f'<Relationship Id="r1" Type="{NS_R}/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            f'<w:document xmlns:w="{NS_W}" xmlns:r="{NS_R}"><w:body>{body_xml}<w:sectPr/></w:body></w:document>'
        ),
        "word/_rels/document.xml.rels": f'<Relationships xmlns="{NS_PKG_REL}"/>',
    }
    if extra_entries:
        entries.update(extra_entries)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()
