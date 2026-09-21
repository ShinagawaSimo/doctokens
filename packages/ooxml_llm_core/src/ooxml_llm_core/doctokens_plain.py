"""Versioned plain-text envelope and DOCX page-marker helpers."""

from __future__ import annotations

import re

_LEGACY_DENSITY_LINE = re.compile(r"^density=plain\r?\n")
_PAGE_MARKER_LINE = re.compile(r"^<page=(?P<number>[1-9][0-9]*)>$")
_PAGE_TOKEN = "\x00doctokens-page:"
_PAGE_TOKEN_END = "\x00"


def page_marker(page: int) -> str:
    """Return an internal marker that cannot collide with source text."""
    if page < 1:
        raise ValueError("page marker must be positive")
    return f"{_PAGE_TOKEN}{page}{_PAGE_TOKEN_END}"


def render_plain(
    legacy_text: str,
    *,
    format_name: str,
    revision_view: str | None = None,
    pagination: str | None = None,
) -> str:
    """Add the DTP envelope without reinterpreting legacy plain content."""
    content = _LEGACY_DENSITY_LINE.sub("", legacy_text, count=1)
    content = _escape_user_page_markers(content)
    content = _restore_page_markers(content)

    fields = {
        "density": "plain",
        "format": format_name,
        "syntax": "doctokens-plain/1.0",
    }
    if pagination is not None:
        fields["pagination"] = pagination
    if revision_view is not None:
        fields["revision_view"] = revision_view
    header = " ".join(f"{key}={fields[key]}" for key in sorted(fields))
    return f"{header}\n{content}"


def validate_plain(text: str, *, format_name: str) -> None:
    """Validate the small DTP surface without parsing document text."""
    lines = text.splitlines()
    if not lines:
        raise ValueError("DTP output is empty")
    fields = dict(item.split("=", 1) for item in lines[0].split(" ") if "=" in item)
    if fields.get("density") != "plain":
        raise ValueError("DTP header must declare density=plain")
    if fields.get("format") != format_name:
        raise ValueError("DTP header format does not match output format")
    if fields.get("syntax") != "doctokens-plain/1.0":
        raise ValueError("DTP header must declare doctokens-plain/1.0")

    previous_page = 0
    for line in lines[1:]:
        match = _PAGE_MARKER_LINE.fullmatch(line)
        if match is not None:
            page = int(match.group("number"))
            if page <= previous_page:
                raise ValueError("DTP page markers must be strictly increasing")
            previous_page = page
        elif line.startswith("\\<page=") and _PAGE_MARKER_LINE.fullmatch(line[1:]) is None:
            raise ValueError("DTP page-marker escape must protect a complete marker line")


def _escape_user_page_markers(content: str) -> str:
    escaped_lines: list[str] = []
    for line in content.splitlines(keepends=True):
        line_body = line.rstrip("\r\n")
        newline = line[len(line_body) :]
        # A literal escape prefix must itself be escaped before reserving the
        # marker form, otherwise consumers cannot recover the source text.
        if line_body.startswith("\\<page=") and _PAGE_MARKER_LINE.fullmatch(line_body[1:]):
            escaped_lines.append(f"\\{line_body}{newline}")
            continue
        if _PAGE_MARKER_LINE.fullmatch(line_body):
            escaped_lines.append(f"\\{line_body}{newline}")
        else:
            escaped_lines.append(line)
    return "".join(escaped_lines)


def _restore_page_markers(content: str) -> str:
    pattern = re.compile(re.escape(_PAGE_TOKEN) + r"([1-9][0-9]*)" + re.escape(_PAGE_TOKEN_END))
    return pattern.sub(lambda match: f"<page={match.group(1)}>", content)


__all__ = ["page_marker", "render_plain", "validate_plain"]
