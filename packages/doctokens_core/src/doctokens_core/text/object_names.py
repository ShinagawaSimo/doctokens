"""Conservative filtering of explicitly permitted English default-name forms."""

import re
from collections.abc import Collection

_NUMBER = re.compile(r"[1-9][0-9]*\Z")


def reading_object_name(name: str | None, prefixes: Collection[str]) -> str | None:
    """Keep nonmatching names verbatim; this is not proof of author provenance."""
    if name is None:
        return None
    prefix, separator, number = name.rpartition(" ")
    if separator and prefix in prefixes and _NUMBER.fullmatch(number):
        return None
    return name
