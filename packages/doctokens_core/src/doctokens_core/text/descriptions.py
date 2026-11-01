"""Select readable object descriptions and names without fabricating text."""

import re
from collections.abc import Collection

_NUMBER = re.compile(r"[1-9][0-9]*\Z")


def first_readable(*values: str | None) -> str | None:
    """Skip whitespace-only candidates while preserving meaningful spacing."""
    return next((value for value in values if value is not None and value.strip()), None)


def reading_object_name(name: str | None, prefixes: Collection[str]) -> str | None:
    """Keep nonmatching names verbatim; this is not proof of author provenance."""
    if name is None:
        return None
    prefix, separator, number = name.rpartition(" ")
    if separator and prefix in prefixes and _NUMBER.fullmatch(number):
        return None
    return name
