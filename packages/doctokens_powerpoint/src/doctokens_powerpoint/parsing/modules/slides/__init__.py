"""PPTX slide and DrawingML text modules."""

from .scanner import SlideParser
from .text import DrawingTextParser

__all__ = ["DrawingTextParser", "SlideParser"]
