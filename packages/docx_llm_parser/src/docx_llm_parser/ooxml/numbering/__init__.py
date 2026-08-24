"""Word numbering support.

The package separates immutable models, format rendering, definition parsing,
counter state, and revision-time numbering changes into focused modules.
"""

from .change import parse_numbering_change
from .formats import NumberFormatRenderer
from .models import NumberingInstance, NumberingLevel
from .parser import NumberingMap, NumberingParser
from .state import NumberingState

__all__ = [
    "NumberFormatRenderer",
    "NumberingInstance",
    "NumberingLevel",
    "NumberingMap",
    "NumberingParser",
    "NumberingState",
    "parse_numbering_change",
]
