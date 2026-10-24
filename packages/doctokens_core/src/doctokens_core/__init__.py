"""Public exports for doctokens_core."""

from doctokens_core._version import __version__
from doctokens_core.doctokens_plain import validate_plain
from doctokens_core.doctokens_xml import validate_xml
from doctokens_core.memory import ParseMemoryLimitError
from doctokens_core.models import Density, ParseReport, ParseResult, ParseWarning, ResourceDescriptor
from doctokens_core.options import PackageOptions
from doctokens_core.planning import ParsePurpose
from doctokens_core.text_search import TextMatch, TextSearchOptions, TextSearchResult

__all__ = [
    "Density",
    "PackageOptions",
    "ParseMemoryLimitError",
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
