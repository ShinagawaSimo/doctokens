"""Internal markers for present content without a readable representation."""

from xml.etree import ElementTree as ET

UNPARSED = "{urn:doctokens:pptx:unparsed}content"


def unparsed_element(kind: str) -> ET.Element:
    return ET.Element(UNPARSED, {"source": kind})
