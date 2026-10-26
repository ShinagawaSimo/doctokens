"""Bounded, read-only Compound File Binary streams."""

from .reader import CfbReader
from .source import CfbError, CfbLimits, CfbUnsupportedError

__all__ = ["CfbError", "CfbLimits", "CfbReader", "CfbUnsupportedError"]
