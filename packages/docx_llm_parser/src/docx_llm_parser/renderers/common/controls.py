"""Compact rendering helpers for Word content controls."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from ...core.models import ContentControl


def wrap_control(content: str, controls: Sequence[ContentControl], density: str) -> str:
    """Wrap existing content in nested control tags, preserving control order."""
    for control in reversed(controls):
        attrs = _control_attrs(control, density)
        content = f"<control {attrs}>{content}</control>"
    return content


def control_attrs(control: ContentControl, density: str) -> str:
    """Return the compact attribute string used by inline and block wrappers."""
    return _control_attrs(control, density)


def wrap_plain_control(content: str, controls: Sequence[ContentControl]) -> str:
    """Add one compact fill/select hint around plain text without XML noise."""
    for control in reversed(controls):
        label = _plain_label(control)
        content = f"[Control {label}: {content}]"
    return content


def _control_attrs(control: ContentControl, density: str) -> str:
    control_type = str(control.get("controlType") or "unknown")
    attrs = [f"type={escape(control_type, quote=True)}"]
    label = str(control.get("alias") or control.get("tag") or "")
    if label:
        attrs.append(f"label={escape(label, quote=True)}")

    if density == "semantic":
        tag = control.get("tag")
        if tag and tag != label:
            attrs.append(f"tag={escape(tag, quote=True)}")
        lock = control.get("lock")
        if lock:
            attrs.append(f"lock={escape(lock, quote=True)}")
        placeholder = _meaningful_placeholder(control.get("placeholder"))
        if placeholder:
            attrs.append(f"placeholder={escape(placeholder, quote=True)}")
        binding = control.get("binding") or {}
        xpath = binding.get("xpath")
        if xpath:
            attrs.append(f"binding={escape(xpath, quote=True)}")
        if control.get("dateFormat"):
            attrs.append(f"dateFormat={escape(str(control['dateFormat']), quote=True)}")
        if "checked" in control:
            attrs.append("checked" if control["checked"] else "unchecked")
        if control.get("multiLine"):
            attrs.append("multiline")
    else:
        lock = control.get("lock")
        if lock in {"sdtLocked", "contentLocked"}:
            attrs.append("locked")

    options = _option_text(control)
    if options:
        attrs.append(f"choices={escape(options, quote=True)}")
    return " ".join(attrs)


def _plain_label(control: ContentControl) -> str:
    control_type = str(control.get("controlType") or "unknown")
    label = str(control.get("alias") or control.get("tag") or "")
    parts = [control_type]
    if label:
        parts.append(label)
    options = _option_text(control)
    if options:
        parts.append(f"choices={options}")
    if control.get("dateFormat"):
        parts.append(f"format={control['dateFormat']}")
    if "checked" in control:
        parts.append("checked" if control["checked"] else "unchecked")
    if control.get("lock") in {"sdtLocked", "contentLocked"}:
        parts.append("locked")
    return " ".join(parts)


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


def _meaningful_placeholder(value: object) -> str:
    if not isinstance(value, str):
        return ""
    if not value or value.lower() in {"defaultplaceholder", "defaultplaceholder_0"}:
        return ""
    return value


__all__ = ["control_attrs", "wrap_control", "wrap_plain_control"]
