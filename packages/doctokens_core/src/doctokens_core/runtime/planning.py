"""Common intent labels for format-specific parsing plans.

The core deliberately does not define feature flags. OOXML formats have
different expensive features, so each parser owns its own typed plan while
sharing these operation-level intents.
"""

from __future__ import annotations

from enum import Enum


class ParsePurpose(str, Enum):
    """Why a document is being parsed."""

    RENDER = "render"
    SESSION = "session"
    RESOURCE = "resource"


__all__ = ["ParsePurpose"]
