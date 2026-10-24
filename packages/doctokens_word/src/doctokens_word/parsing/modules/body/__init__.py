"""DOCX body parsing modules."""

from .anchors import BlockIdAllocator
from .inline import InlineParser
from .objects import drawing_objects, equation_object, parse_embedded_object
from .runs import RunParser
from .scanner import DocumentBodyParser
from .tables import TableParser
from .vml import pict_objects

__all__ = [
    "BlockIdAllocator",
    "DocumentBodyParser",
    "InlineParser",
    "RunParser",
    "TableParser",
    "drawing_objects",
    "equation_object",
    "parse_embedded_object",
    "pict_objects",
]
