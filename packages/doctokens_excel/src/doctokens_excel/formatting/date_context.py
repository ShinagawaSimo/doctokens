"""Explicit date locales and deterministic system-format defaults.

ISO/IEC 29500-1 section 18.8.30 defines F800/F400 as system formats.
The package does not save the producer's OS preferences, so these defaults
are parser policy, never a lookup of the machine running the parser.
"""

from __future__ import annotations

from typing import NamedTuple

from .sections import _section_directives

_LANGUAGES = {0x0409: "en-us", 0x0804: "zh-cn"}
_LONG_DATES = {"zh-cn": 'yyyy"年"m"月"d"日"', "en-us": "dddd, mmmm d, yyyy"}


def date_locale(section: str, locale: str) -> str:
    """Resolve a supported explicit LCID before the caller's default locale."""
    language = _section_directives(section).language_info
    if language in {None, 0, 0xF800, 0xF400}:
        return locale.replace("_", "-").lower()
    if language not in _LANGUAGES:
        # Do not discard calendar/number-system bits or guess another locale.
        raise ValueError("Unsupported date language/calendar/number system")
    return _LANGUAGES[language]


class DateContext(NamedTuple):
    code: str
    locale: str
    dbnum: str | None


def date_context(section: str, locale: str) -> DateContext:
    directives = _section_directives(section)
    effective_locale = date_locale(section, locale)
    if directives.language_info == 0xF800:
        if effective_locale not in _LONG_DATES:
            raise ValueError("Unsupported system long-date locale")
        section = _LONG_DATES[effective_locale]
    elif directives.language_info == 0xF400:
        # System time is a separate policy, awaiting a real Office fixture.
        raise ValueError("System time format is not yet supported")
    if directives.dbnum and (directives.dbnum not in {"dbnum1", "dbnum2", "dbnum3"} or effective_locale != "zh-cn"):
        raise ValueError("Unsupported date DBNum mode")
    return DateContext(section, effective_locale, directives.dbnum)
