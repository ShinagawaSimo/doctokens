"""Plain control markers and contiguous control-content grouping."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ...model import ContentControl


def wrap_plain_control(content: str, controls: Sequence[ContentControl]) -> str:
    for control in reversed(controls):
        label = control.get("label")
        if not content and "checked" in control:
            content = "checked" if control["checked"] else "unchecked"
        marker = f"[content-control] {label}:" if label else "[content-control]"
        content = f"{marker} {content}" if content else marker
    return content


def controlled_text(segments: Iterable[tuple[str, Sequence[ContentControl]]]) -> str:
    """Keep a control marker once across adjacent formatted source runs."""
    active: list[ContentControl] = []
    buffers: list[list[str]] = [[]]

    def close() -> None:
        value = "".join(buffers.pop())
        buffers[-1].append(wrap_plain_control(value, [active.pop()]))

    for value, controls in segments:
        shared = 0
        while shared < min(len(active), len(controls)) and active[shared] is controls[shared]:
            shared += 1
        while len(active) > shared:
            close()
        for control in controls[shared:]:
            active.append(control)
            buffers.append([])
        buffers[-1].append(value)
    while active:
        close()
    return "".join(buffers[0])
