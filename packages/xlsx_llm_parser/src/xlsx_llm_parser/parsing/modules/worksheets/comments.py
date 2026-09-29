"""Comments."""

from __future__ import annotations

from collections.abc import Mapping
from xml.etree import ElementTree as ET

from ooxml_llm_core.annotations import AnnotationMention, valid_parent_links
from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader
from ooxml_llm_core.xml import local_name

from ...._utils import parse_ref
from ....models import (
    Cell,
    ThreadedComment,
)
from .post_common import NS_R, NS_S, _as_bool, _ensure_cell, _safe_int, _warn

_REL_COMMENTS = f"{NS_R}/comments"


_REL_THREADED_COMMENTS = "http://schemas.microsoft.com/office/2017/10/relationships/threadedComment"


# ── Comments ──


def apply_comments(
    cell_map: dict[int, Cell],
    pkg: PackageReader,
    sheet_rels: list[RelationshipRecord],
    rows: list[list[Cell]] | None = None,
    rows_by_number: dict[int, list[Cell]] | None = None,
    threaded_comment_people: Mapping[str, str] | None = None,
    warnings: list[ParseWarning] | None = None,
) -> None:
    """Parse legacy and threaded comments, keeping each collaboration thread on its cell."""
    # Find comments part via pre-read sheet relationships
    comments_rel = next((rel for rel in sheet_rels if rel.type == _REL_COMMENTS), None)
    comments_part = comments_rel.resolved_target if comments_rel is not None else None
    if comments_rel is not None and (not comments_part or not pkg.exists(comments_part)):
        _warn(
            warnings,
            "COMMENTS_PART_MISSING",
            "Referenced comments part is missing",
            f"{comments_rel.source_part}#{comments_rel.id}",
        )
    if comments_part is not None and pkg.exists(comments_part):
        try:
            root = pkg.read_xml(comments_part)
        except ET.ParseError as exc:
            _warn(warnings, "COMMENTS_XML_INVALID", f"Invalid comments XML: {exc}", comments_part)
            root = None
        if root is not None:
            _apply_legacy_comments(root, cell_map, rows, rows_by_number)

    _apply_threaded_comments(cell_map, pkg, sheet_rels, rows, rows_by_number, threaded_comment_people or {}, warnings)


def _apply_legacy_comments(
    root: ET.Element,
    cell_map: dict[int, Cell],
    rows: list[list[Cell]] | None,
    rows_by_number: dict[int, list[Cell]] | None,
) -> None:
    """Attach legacy note-style comments while leaving threaded comments independent."""
    authors: list[str] = []
    authors_elem = root.find(f"{{{NS_S}}}authors")
    if authors_elem is not None:
        authors.extend(a.text or "" for a in authors_elem.findall(f"{{{NS_S}}}author"))
    comment_list = root.find(f"{{{NS_S}}}commentList")
    if comment_list is None:
        return
    for comment in comment_list.findall(f"{{{NS_S}}}comment"):
        ref = comment.get("ref", "")
        try:
            col, row = parse_ref(ref)
        except ValueError:
            continue
        cell = _ensure_cell(cell_map, rows, rows_by_number, ref, col, row)
        if cell is None:
            continue
        author_id_str = comment.get("authorId", "0")
        try:
            author_id = int(author_id_str)
            cell["commentAuthor"] = authors[author_id] if author_id < len(authors) else ""
        except (ValueError, IndexError):
            cell["commentAuthor"] = ""
        text_elem = comment.find(f"{{{NS_S}}}text")
        if text_elem is None:
            cell["comment"] = ""
        else:
            cell["comment"] = "".join(text_elem.itertext())


def parse_threaded_comment_people(pkg: PackageReader, warnings: list[ParseWarning] | None = None) -> dict[str, str]:
    """Read the workbook-wide people catalog once for modern comment authors and mentions."""
    part = "xl/persons/person.xml"
    if not pkg.exists(part):
        return {}
    try:
        root = pkg.read_xml(part)
    except ET.ParseError as exc:
        _warn(warnings, "COMMENT_PEOPLE_XML_INVALID", f"Invalid comment people XML: {exc}", part)
        return {}
    people: dict[str, str] = {}
    for element in root.iter():
        if local_name(element.tag) != "person":
            continue
        person_id = element.get("id")
        display_name = element.get("displayName")
        if person_id and display_name:
            people[person_id] = display_name
    return people


def _apply_threaded_comments(
    cell_map: dict[int, Cell],
    pkg: PackageReader,
    sheet_rels: list[RelationshipRecord],
    rows: list[list[Cell]] | None,
    rows_by_number: dict[int, list[Cell]] | None,
    people: Mapping[str, str],
    warnings: list[ParseWarning] | None = None,
) -> None:
    """Attach one modern comment conversation to its target cell without a package-wide scan."""
    rel = next((rel for rel in sheet_rels if rel.type == _REL_THREADED_COMMENTS), None)
    if rel is None:
        return
    part = rel.resolved_target
    if not part or not pkg.exists(part):
        _warn(
            warnings,
            "THREADED_COMMENTS_PART_MISSING",
            "Referenced threaded comments part is missing",
            f"{rel.source_part}#{rel.id}",
        )
        return
    try:
        root = pkg.read_xml(part)
    except ET.ParseError as exc:
        _warn(warnings, "THREADED_COMMENTS_XML_INVALID", f"Invalid threaded comments XML: {exc}", part)
        return

    pending: list[tuple[ThreadedComment, str, str | None]] = []
    raw_to_display: dict[str, str] = {}
    per_cell_index: dict[str, int] = {}
    for element in root:
        if local_name(element.tag) != "threadedComment":
            continue
        ref = element.get("ref", "")
        try:
            col, row = parse_ref(ref)
        except ValueError:
            continue
        cell = _ensure_cell(cell_map, rows, rows_by_number, ref, col, row)
        if cell is None:
            continue
        ordinal = per_cell_index.get(ref, 0) + 1
        per_cell_index[ref] = ordinal
        item: ThreadedComment = {"id": f"thread-{ref}-{ordinal}", "text": _threaded_comment_text(element)}
        author = people.get(element.get("personId", ""), "")
        if author:
            item["author"] = author
        date = element.get("dT")
        if date:
            item["date"] = date
        if _as_bool(element.get("done")):
            item["resolved"] = True
        mentions = _threaded_mentions(element, people)
        if mentions:
            item["mentions"] = mentions
        raw_id = element.get("id") or item["id"]
        raw_to_display[raw_id] = item["id"]
        pending.append((item, raw_id, element.get("parentId")))
        cell.setdefault("threadedComments", []).append(item)

    links, _dangling = valid_parent_links((raw_id, parent_id) for _item, raw_id, parent_id in pending)
    for item, raw_id, _parent_id in pending:
        parent_raw_id = links.get(raw_id)
        if parent_raw_id:
            item["parentId"] = raw_to_display[parent_raw_id]


def _threaded_comment_text(element: ET.Element) -> str:
    text_node = next((child for child in element if local_name(child.tag) == "text"), None)
    return "".join(text_node.itertext()) if text_node is not None else ""


def _threaded_mentions(element: ET.Element, people: Mapping[str, str]) -> list[AnnotationMention]:
    mentions: list[AnnotationMention] = []
    for descendant in element.iter():
        if local_name(descendant.tag) != "mention":
            continue
        person = people.get(descendant.get("personId", ""), "")
        if not person:
            continue
        mention: AnnotationMention = {"person": person}
        start = _safe_int(descendant.get("startIndex"))
        length = _safe_int(descendant.get("length"))
        if start is not None:
            mention["start"] = start
        if length is not None:
            mention["length"] = length
        mentions.append(mention)
    return mentions
