"""Public exports for doctokens_core."""

from ._version import __version__
from .containers.opc.options import PackageOptions
from .contracts.models import Density, ParseReport, ParseResult, ParseWarning, ResourceDescriptor
from .output.plain import validate_plain
from .output.xml import validate_xml
from .runtime.memory import ParseMemoryLimitError
from .runtime.planning import ParsePurpose
from .text.search import TextMatch, TextSearchOptions, TextSearchResult

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
