"""Attach saved presentation comments to their slides and source shapes."""

from __future__ import annotations

from ..core.models import CommentItem, CommentRef, SlideBlock
from .slide_sequence import _SlideReference


def attach_comments(
    comments: list[CommentItem],
    slides: list[SlideBlock],
    slide_size: tuple[int, int] | None,
    *,
    infer_single: bool = True,
) -> None:
    """Resolve comment slide/shape references without discarding raw IDs."""
    slide_by_locator = {locator: slide for slide in slides for locator in (slide["id"], slide["part"], slide["sldId"]) if locator}
    for comment in comments:
        locator = comment.get("slideId")
        slide = slide_by_locator.get(locator) if isinstance(locator, str) else None
        if slide is None and infer_single and len(slides) == 1:
            slide = slides[0]
        if slide is None:
            continue
        comment["slideId"] = slide["id"]
        reference: CommentRef = {"id": comment["id"]}
        x = comment.get("x")
        y = comment.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            if reference not in slide["commentRefs"]:
                slide["commentRefs"].append(reference)
            continue
        if slide_size is not None and (abs(x) > 1000 or abs(y) > 1000):
            x = round(x / slide_size[0] * 1000)
            y = round(y / slide_size[1] * 1000)
        positioned = [shape for shape in slide["shapes"] if shape.get("x") is not None and shape.get("y") is not None]
        if positioned:
            nearest = min(
                positioned,
                key=lambda shape: abs(shape["x"] + shape.get("w", 0) // 2 - x) + abs(shape["y"] + shape.get("h", 0) // 2 - y),
            )
            comment["shapeId"] = nearest["id"]
            reference["shapeId"] = nearest["id"]
        if reference not in slide["commentRefs"]:
            slide["commentRefs"].append(reference)


class _CommentAttachmentPlan:
    """Group raw comments by validated slide locator before slide parsing."""

    def __init__(self, comments: list[CommentItem], refs: tuple[_SlideReference, ...]) -> None:
        self.by_slide_part: dict[str, list[CommentItem]] = {}
        self.unresolved: list[CommentItem] = []
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
            if part is None:
                self.unresolved.append(comment)
            else:
                self.by_slide_part.setdefault(part, []).append(comment)

    def attach(self, slide: SlideBlock, slide_size: tuple[int, int] | None) -> None:
        comments = self.by_slide_part.pop(slide["part"], [])
        if comments:
            attach_comments(comments, [slide], slide_size, infer_single=False)

    def attach_all(self, slides: list[SlideBlock], slide_size: tuple[int, int] | None) -> None:
        for slide in slides:
            self.attach(slide, slide_size)
        if self.unresolved and len(slides) == 1:
            attach_comments(self.unresolved, slides, slide_size, infer_single=True)
