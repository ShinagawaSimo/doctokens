"""Public exports for ooxml_llm_core."""

from ooxml_llm_core._version import __version__
from ooxml_llm_core.doctokens_plain import validate_plain
from ooxml_llm_core.doctokens_xml import validate_xml
from ooxml_llm_core.models import Density, ParseReport, ParseResult, ParseWarning, ResourceDescriptor
from ooxml_llm_core.options import PackageOptions
from ooxml_llm_core.planning import ParsePurpose
from ooxml_llm_core.text_search import TextMatch, TextSearchOptions, TextSearchResult

__all__ = [
    "Density",
    "PackageOptions",
    "ParsePurpose",
    "ParseReport",
    "ParseResult",
    "ParseWarning",
    "ResourceDescriptor",
    "TextMatch",
    "TextSearchOptions",
    "TextSearchResult",
    "__version__",
    "validate_plain",
    "validate_xml",
]
