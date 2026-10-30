"""Normalize saved slide-link targets consistently in shapes and comments."""

from __future__ import annotations

from collections.abc import Mapping


def normalize_link(target: str, targets: Mapping[str, str], slide_number: int | None, slide_count: int) -> str:
    if target in targets:
        return targets[target]
    marker = "ppaction://hlinkshowjump?jump="
    if not target.startswith(marker) or not slide_count:
        return target
    jump = target.removeprefix(marker).lower()
    target_index = {"firstslide": 1, "lastslide": slide_count}.get(jump)
    if slide_number is not None:
        if jump == "nextslide":
            target_index = min(slide_number + 1, slide_count)
        elif jump == "previousslide":
            target_index = max(slide_number - 1, 1)
    return f"#slide{target_index}" if target_index else target
