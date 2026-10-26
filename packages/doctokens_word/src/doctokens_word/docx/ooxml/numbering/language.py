"""Locale-specific numbering rules covered by WordprocessingML examples.

The OOXML type delegates these formats to ``w:lang`` but does not define a
universal natural-language algorithm.  This module keeps the supported locale
table explicit and lets callers fall back to the historical English/ASCII
renderers when a locale is not covered.
"""

from __future__ import annotations

from collections.abc import Callable


def language_base(language: str | None) -> str:
    """Return a normalized BCP 47 primary language subtag."""
    return (language or "").replace("_", "-").split("-", 1)[0].lower()


def latin_alphabet(language: str | None, *, upper: bool) -> str | None:
    """Return the locale-specific Latin alphabet when OOXML defines one."""
    alphabets = {
        "nb": "abcdefghijklmnopqrstuvwxyzæøå",
        "nn": "abcdefghijklmnopqrstuvwxyzæøå",
        "no": "abcdefghijklmnopqrstuvwxyzæøå",
    }
    alphabet = alphabets.get(language_base(language))
    return alphabet.upper() if alphabet and upper else alphabet


def cardinal_text(value: int, language: str | None, english: Callable[[int], str]) -> str:
    """Render cardinal text for the documented Spanish example or English."""
    if language_base(language) == "es":
        return _spanish_cardinal(value)
    return english(value)


def ordinal(value: int, language: str | None, english: Callable[[int], str]) -> str:
    """Render numeric ordinals for the documented French example or English."""
    if language_base(language) == "fr":
        return f"{value}er" if value == 1 else f"{value}e"
    return english(value)


def ordinal_text(value: int, language: str | None, english: Callable[[int], str]) -> str:
    """Render ordinal words for the documented German example or English."""
    if language_base(language) == "de":
        return _german_ordinal(value)
    return english(value)


def _spanish_cardinal(value: int) -> str:
    if not 0 <= value <= 999_999:
        return ""
    under_thirty = (
        "cero",
        "uno",
        "dos",
        "tres",
        "cuatro",
        "cinco",
        "seis",
        "siete",
        "ocho",
        "nueve",
        "diez",
        "once",
        "doce",
        "trece",
        "catorce",
        "quince",
        "dieciseis",
        "diecisiete",
        "dieciocho",
        "diecinueve",
        "veinte",
        "veintiuno",
        "veintidos",
        "veintitres",
        "veinticuatro",
        "veinticinco",
        "veintiseis",
        "veintisiete",
        "veintiocho",
        "veintinueve",
    )
    tens = ("", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
    hundreds = (
        "",
        "",
        "doscientos",
        "trescientos",
        "cuatrocientos",
        "quinientos",
        "seiscientos",
        "setecientos",
        "ochocientos",
        "novecientos",
    )

    def under_thousand(number: int) -> str:
        if number < 30:
            return under_thirty[number]
        if number < 100:
            return tens[number // 10] if number % 10 == 0 else f"{tens[number // 10]} y {under_thirty[number % 10]}"
        quotient, remainder = divmod(number, 100)
        prefix = "cien" if quotient == 1 and remainder == 0 else "ciento" if quotient == 1 else hundreds[quotient]
        return prefix if not remainder else f"{prefix} {under_thousand(remainder)}"

    if value < 1000:
        return under_thousand(value).title()
    thousands, remainder = divmod(value, 1000)
    prefix = "mil" if thousands == 1 else f"{under_thousand(thousands)} mil"
    return (prefix if not remainder else f"{prefix} {under_thousand(remainder)}").title()


def _german_ordinal(value: int) -> str:
    if value < 0:
        return str(value)
    direct = (
        "Nullte",
        "Erste",
        "Zweite",
        "Dritte",
        "Vierte",
        "Fünfte",
        "Sechste",
        "Siebte",
        "Achte",
        "Neunte",
        "Zehnte",
        "Elfte",
        "Zwölfte",
        "Dreizehnte",
        "Vierzehnte",
        "Fünfzehnte",
        "Sechzehnte",
        "Siebzehnte",
        "Achtzehnte",
        "Neunzehnte",
        "Zwanzigste",
    )
    if value < len(direct):
        return direct[value]

    units = ("", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun")
    tens = ("", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig")
    if value < 100:
        quotient, remainder = divmod(value, 10)
        stem = tens[quotient] if not remainder else f"{units[remainder]}und{tens[quotient]}"
        return (stem + "ste").title()
    if value < 1000:
        quotient, remainder = divmod(value, 100)
        stem = f"{units[quotient] or 'ein'}hundert"
        return (stem + ("ste" if not remainder else _german_ordinal(remainder).lower())).title()
    quotient, remainder = divmod(value, 1000)
    prefix = "eintausend" if quotient == 1 else f"{_german_ordinal(quotient).removesuffix('te').lower()}tausend"
    return (prefix + ("ste" if not remainder else _german_ordinal(remainder).lower())).title()


__all__ = ["cardinal_text", "language_base", "latin_alphabet", "ordinal", "ordinal_text"]
