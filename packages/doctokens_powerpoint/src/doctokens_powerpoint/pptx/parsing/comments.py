"""Attach comments through validated slide ownership and exact source identities."""

from __future__ import annotations

from ..model.presentation import CommentItem, CommentRef, SlideBlock
from .comment_anchors import matches_shape
from .navigation import normalize_link
from .slide_sequence import _SlideReference


def attach_comments(comments: list[CommentItem], slides: list[SlideBlock]) -> None:
    slide_by_locator = {locator: slide for slide in slides for locator in (slide["id"], slide["part"], slide["sldId"]) if locator}
    by_id = {item["id"]: item for item in comments}
    for comment in comments:
        locator = comment.get("slideId")
        slide = slide_by_locator.get(locator) if isinstance(locator, str) else None
        if slide is None:
            continue
        comment["slideId"] = slide["id"]
        reference: CommentRef = {"id": comment["id"]}
        if "target" in comment:
            targets = [shape for shape in slide["shapes"] if matches_shape(comment["target"], shape)]
            if len(targets) == 1:
                comment["shapeId"] = targets[0]["id"]
                reference["shapeId"] = targets[0]["id"]
        elif parent_shape := by_id.get(comment.get("parentCommentId", ""), {}).get("shapeId"):
            comment["shapeId"] = parent_shape
            reference["shapeId"] = parent_shape
        if reference not in slide["commentRefs"]:
            slide["commentRefs"].append(reference)


class _CommentAttachmentPlan:
    """Group saved comments by validated slide owner before attaching targets."""

    def __init__(self, comments: list[CommentItem], refs: tuple[_SlideReference, ...]) -> None:
        self._comments = comments
        self._targets = {ref.part: f"#slide{index}" for index, ref in enumerate(refs, 1)}
        self.by_slide_part: dict[str, list[CommentItem]] = {}
        by_locator: dict[str, str] = {}
        for index, ref in enumerate(refs, start=1):
            by_locator[ref.part] = ref.part
            by_locator[ref.relationship_id] = ref.part
            if ref.slide_id:
                by_locator[ref.slide_id] = ref.part
            by_locator[f"slide{index}"] = ref.part
        for comment in comments:
            locator = comment.get("slideId")
            part = by_locator.get(locator) if isinstance(locator, str) else None
            if part is not None:
                self.by_slide_part.setdefault(part, []).append(comment)

    def attach_all(self, slides: list[SlideBlock]) -> None:
        for slide in slides:
            comments = self.by_slide_part.pop(slide["part"], [])
            if comments:
                attach_comments(comments, [slide])
        numbers = {slide["id"]: slide["n"] for slide in slides}
        for comment in self._comments:
            for run in comment.get("runs", []):
                if link := run.get("link"):
                    run["link"] = normalize_link(link, self._targets, numbers.get(comment.get("slideId", "")), len(self._targets))
