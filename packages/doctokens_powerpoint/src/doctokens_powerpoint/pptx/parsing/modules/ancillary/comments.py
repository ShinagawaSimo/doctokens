"""Read classic PresentationML and modern PowerPoint comment parts."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_core.contracts.models import ParseWarning

from ....model.presentation import CommentItem, Run
from ....ooxml.compatibility import read_content_part
from ....ooxml.namespaces import NS
from ....ooxml.package import PackageReader
from ...comment_anchors import MODERN_NS, read_anchors, walk_anchors
from ..slides.runs import paragraph_runs

_CLASSIC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
_MODERN_REL = "http://schemas.microsoft.com/office/2018/10/relationships/"
_FAMILIES = (
    (_CLASSIC_REL + "comments", _CLASSIC_REL + "commentAuthors", NS["p"], "cmAuthor"),
    (_MODERN_REL + "comments", _MODERN_REL + "authors", MODERN_NS, "author"),
)


class CommentsParser:
    """Use exact source namespaces and direct bodies; never mix reply bodies."""

    def __init__(self, pkg: PackageReader, relationships: RelationshipIndex, warnings: list[ParseWarning]) -> None:
        self._pkg = pkg
        self._relationships = relationships
        self._warnings = warnings

    def parse(self) -> list[CommentItem]:
        comments: list[CommentItem] = []
        for comments_rel, authors_rel, namespace, author_tag in _FAMILIES:
            modern = namespace == MODERN_NS
            authors = self._read_authors(authors_rel, namespace, author_tag)
            seen: set[tuple[str, str]] = set()
            for record in self._relationships.by_type(comments_rel):
                part = record.resolved_target
                if part is None or not self._pkg.exists(part):
                    self._warnings.append(
                        ParseWarning(
                            "COMMENTS_PART_MISSING",
                            f"Comments part missing: {part}",
                            record.source_part,
                        )
                    )
                    comments.append(self._unparsed(len(comments) + 1, record.source_part, modern))
                    continue
                if (record.source_part, part) in seen:
                    continue
                seen.add((record.source_part, part))
                try:
                    root = read_content_part(self._pkg, part, self._warnings)
                except ET.ParseError as exc:
                    self._warnings.append(ParseWarning("COMMENTS_XML_INVALID", f"Invalid comments XML: {exc}", part))
                    comments.append(self._unparsed(len(comments) + 1, record.source_part, modern))
                    continue
                if root.tag != f"{{{namespace}}}cmLst":
                    self._warnings.append(
                        ParseWarning("COMMENTS_ROOT_UNSUPPORTED", f"Unsupported comments root: {root.tag}", part)
                    )
                    comments.append(self._unparsed(len(comments) + 1, record.source_part, modern))
                    continue
                if not modern:
                    self._warnings.append(
                        ParseWarning(
                            "LEGACY_COMMENTS_PARSED",
                            "Legacy comments were parsed without modern thread metadata",
                            part,
                        )
                    )
                for element in root:
                    if element.tag != f"{{{namespace}}}cm":
                        if element.tag == f"{{{namespace}}}extLst":
                            continue
                        self._warnings.append(
                            ParseWarning(
                                "COMMENT_ELEMENT_UNSUPPORTED",
                                f"Unsupported comment element: {element.tag}",
                                part,
                            )
                        )
                        comments.append(self._unparsed(len(comments) + 1, record.source_part, modern))
                        continue
                    item = self._item(element, authors, part, modern)
                    item["id"] = f"cmt{len(comments) + 1}"
                    if record.source_part.startswith("ppt/slides/"):
                        item["slideId"] = record.source_part
                    if modern:
                        anchors = read_anchors(element)
                        if anchors:
                            item["anchors"] = anchors
                        slide_id = next(
                            (
                                a["attributes"].get("sldId")
                                for a in walk_anchors(anchors)
                                if a["kind"] == "sldMk" and a["attributes"].get("sldId")
                            ),
                            None,
                        )
                        if slide_id:
                            item["slideId"] = slide_id
                    comments.append(item)
                    replies = element.find(f"{{{MODERN_NS}}}replyLst") if modern else None
                    if replies is not None:
                        for reply in replies:
                            if reply.tag == f"{{{MODERN_NS}}}reply":
                                child = self._item(reply, authors, part, True)
                            elif reply.tag == f"{{{MODERN_NS}}}extLst":
                                continue
                            else:
                                self._warnings.append(
                                    ParseWarning(
                                        "COMMENT_ELEMENT_UNSUPPORTED",
                                        f"Unsupported reply element: {reply.tag}",
                                        part,
                                    )
                                )
                                child = self._unparsed(len(comments) + 1, record.source_part, True)
                            child["id"] = f"cmt{len(comments) + 1}"
                            child["parentCommentId"] = item["id"]
                            if "slideId" in item:
                                child["slideId"] = item["slideId"]
                            comments.append(child)
        return comments

    def _item(self, node: ET.Element, authors: dict[str, str], part: str, modern: bool) -> CommentItem:
        namespace = MODERN_NS if modern else NS["p"]
        body = node.find(f"{{{namespace}}}{'txBody' if modern else 'text'}")
        runs = _body_runs(body, part, self._warnings) if modern else []
        value = "".join(run.get("text", "") for run in runs) if modern else "".join(body.itertext()) if body is not None else ""
        item: CommentItem = {"text": value, "author": authors.get(node.get("authorId", ""), "")}
        if any("unparsed" in run or "equation" in run for run in runs):
            item["runs"] = runs
        if modern:
            item["modern"] = True
            status = node.get("status", "active")
            if status in {"active", "resolved", "closed"}:
                item["status"] = status
            else:
                self._warnings.append(ParseWarning("COMMENT_STATUS_INVALID", f"Invalid comment status: {status}", part))
        if date := node.get("created" if modern else "dt"):
            item["date"] = date
        position = node.find(f"{{{namespace}}}pos")
        if position is not None:
            for key in ("x", "y"):
                raw = position.get(key)
                if raw is not None:
                    try:
                        item[key] = int(raw)
                    except ValueError:
                        self._warnings.append(ParseWarning("COMMENT_POSITION_INVALID", f"Invalid {key}: {raw}", part))
        return item

    @staticmethod
    def _unparsed(index: int, source: str, modern: bool) -> CommentItem:
        item: CommentItem = {"id": f"cmt{index}", "text": "[Unparsed comments]", "unparsed": True}
        if modern:
            item["modern"] = True
        if source.startswith("ppt/slides/"):
            item["slideId"] = source
        return item

    def _read_authors(self, relationship: str, namespace: str, tag: str) -> dict[str, str]:
        authors: dict[str, str] = {}
        for record in self._relationships.by_type(relationship):
            part = record.resolved_target
            if part is None or not self._pkg.exists(part):
                continue
            try:
                root = self._pkg.read_xml(part)
            except ET.ParseError:
                continue
            for node in root.findall(f"{{{namespace}}}{tag}"):
                if (identifier := node.get("id")) and (name := node.get("name")):
                    authors[identifier] = name
        return authors


def _body_runs(body: ET.Element | None, part: str, warnings: list[ParseWarning]) -> list[Run]:
    """Preserve empty paragraphs, whitespace and saved field text without list guesses."""
    if body is None:
        return []
    runs: list[Run] = []
    a = f"{{{NS['a']}}}"
    first = True
    for child in body:
        if child.tag in {a + "bodyPr", a + "lstStyle"}:
            continue
        if not first:
            runs.append({"text": "\n"})
        first = False
        if child.tag == a + "p":
            runs.extend(paragraph_runs(child, part, warnings, {}, {}, {}, include_formatting=False))
        else:
            warnings.append(ParseWarning("COMMENT_BODY_CHILD_UNSUPPORTED", f"Unsupported comment body child: {child.tag}", part))
            runs.append({"text": "[Unparsed comment content]", "unparsed": "comment-content"})
    return runs
