"""Compact rendering helpers for Word content controls."""

from __future__ import annotations

from collections.abc import Sequence

from ...model import ContentControl


def wrap_plain_control(content: str, controls: Sequence[ContentControl]) -> str:
    """Add one compact fill/select hint around plain text without XML noise."""
    for control in reversed(controls):
        label = _plain_label(control)
        content = f"[Control {label}: {content}]"
    return content


def _plain_label(control: ContentControl) -> str:
    control_type = str(control.get("controlType") or "unknown")
    label = str(control.get("alias") or control.get("tag") or "")
    label_parts = [control_type]
    if label:
        label_parts.append(label)
    options = _option_text(control)
    if options:
        label_parts.append(f"choices={options}")
    if control.get("dateFormat"):
        label_parts.append(f"format={control['dateFormat']}")
    if "checked" in control:
        label_parts.append("checked" if control["checked"] else "unchecked")
    if control.get("lock") in {"sdtLocked", "contentLocked"}:
        label_parts.append("locked")
    return " ".join(label_parts)


def _option_text(control: ContentControl) -> str:
    options = control.get("options") or []
    values: list[str] = []
    for option in options:
        display = str(option.get("display") or "")
        value = str(option.get("value") or "")
        if display and value and display != value:
            values.append(f"{display}={value}")
        elif display or value:
            values.append(display or value)
    return "|".join(values)


__all__ = ["wrap_plain_control"]
