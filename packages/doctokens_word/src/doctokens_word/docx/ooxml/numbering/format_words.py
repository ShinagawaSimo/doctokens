"""Format words."""

from __future__ import annotations

from .format_codes import _MAX_WORD_VALUE


def _english_cardinal(value: int) -> str:
    if value < 0 or value > 999_999:
        return ""
    ones = (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    )
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")

    def under_thousand(number: int) -> str:
        if number < 20:
            return ones[number]
        if number < 100:
            quotient, remainder = divmod(number, 10)
            return tens[quotient] if not remainder else f"{tens[quotient]}-{ones[remainder]}"
        quotient, remainder = divmod(number, 100)
        return f"{ones[quotient]} hundred" if not remainder else f"{ones[quotient]} hundred {under_thousand(remainder)}"

    if value < 1000:
        return under_thousand(value).title()
    quotient, remainder = divmod(value, 1000)
    result = f"{under_thousand(quotient)} thousand"
    return result.title() if not remainder else f"{result} {under_thousand(remainder)}".title()


def _english_ordinal(value: int) -> str:
    if value < 0 or value > 999_999:
        return ""
    special = {
        "zero": "zeroth",
        "one": "first",
        "two": "second",
        "three": "third",
        "four": "fourth",
        "five": "fifth",
        "six": "sixth",
        "seven": "seventh",
        "eight": "eighth",
        "nine": "ninth",
        "ten": "tenth",
        "eleven": "eleventh",
        "twelve": "twelfth",
        "thirteen": "thirteenth",
        "fourteen": "fourteenth",
        "fifteen": "fifteenth",
        "sixteen": "sixteenth",
        "seventeen": "seventeenth",
        "eighteen": "eighteenth",
        "nineteen": "nineteenth",
        "twenty": "twentieth",
        "thirty": "thirtieth",
        "forty": "fortieth",
        "fifty": "fiftieth",
        "sixty": "sixtieth",
        "seventy": "seventieth",
        "eighty": "eightieth",
        "ninety": "ninetieth",
        "hundred": "hundredth",
        "thousand": "thousandth",
    }
    cardinal = _english_cardinal(value).lower()
    prefix, separator, tail = cardinal.rpartition("-")
    if separator:
        return f"{prefix}-{special.get(tail, tail + 'th')}"
    prefix, separator, tail = cardinal.rpartition(" ")
    ordinal_tail = special.get(tail, tail + "th")
    return (f"{prefix} {ordinal_tail}" if separator else ordinal_tail).title()


def _hindi_counting(value: int) -> str:
    if value < 0:
        return str(value)
    if value > _MAX_WORD_VALUE:
        return ""

    words = (
        "शून्य",
        "एक",
        "दो",
        "तीन",
        "चार",
        "पाँच",
        "छह",
        "सात",
        "आठ",
        "नौ",
        "दस",
        "ग्यारह",
        "बारह",
        "तेरह",
        "चौदह",
        "पंद्रह",
        "सोलह",
        "सत्रह",
        "अठारह",
        "उन्नीस",
        "बीस",
        "इक्कीस",
        "बाईस",
        "तेईस",
        "चौबीस",
        "पच्चीस",
        "छब्बीस",
        "सत्ताईस",
        "अट्ठाईस",
        "उनतीस",
        "तीस",
        "इकतीस",
        "बत्तीस",
        "तैंतीस",
        "चौंतीस",
        "पैंतीस",
        "छत्तीस",
        "सैंतीस",
        "अड़तीस",
        "उनतालीस",
        "चालीस",
        "इकतालीस",
        "बयालीस",
        "तैंतालीस",
        "चवालीस",
        "पैंतालीस",
        "छियालीस",
        "सैंतालीस",
        "अड़तालीस",
        "उनचास",
        "पचास",
        "इक्यावन",
        "बावन",
        "तिरपन",
        "चौवन",
        "पचपन",
        "छप्पन",
        "सत्तावन",
        "अट्ठावन",
        "उनसठ",
        "साठ",
        "इकसठ",
        "बासठ",
        "तिरसठ",
        "चौंसठ",
        "पैंसठ",
        "छियासठ",
        "सड़सठ",
        "अड़सठ",
        "उनहत्तर",
        "सत्तर",
        "इकहत्तर",
        "बहत्तर",
        "तिहत्तर",
        "चौहत्तर",
        "पचहत्तर",
        "छिहत्तर",
        "सतहत्तर",
        "अठहत्तर",
        "उन्नासी",
        "अस्सी",
        "इक्यासी",
        "बयासी",
        "तिरासी",
        "चौरासी",
        "पचासी",
        "छियासी",
        "सतासी",
        "अट्ठासी",
        "नवासी",
        "नब्बे",
        "इक्यानबे",
        "बानबे",
        "तिरानबे",
        "चौरानबे",
        "पंचानबे",
        "छियानबे",
        "सत्तानबे",
        "अट्ठानबे",
        "निन्यानबे",
    )

    def under_hundred(number: int) -> str:
        return words[number]

    def under_thousand(number: int) -> str:
        hundreds, remainder = divmod(number, 100)
        parts: list[str] = []
        if hundreds:
            parts.extend((words[hundreds], "सौ"))
        if remainder:
            parts.append(under_hundred(remainder))
        return " ".join(parts)

    def under_lakh(number: int) -> str:
        thousands, remainder = divmod(number, 1000)
        parts: list[str] = []
        if thousands:
            parts.append(under_hundred(thousands) + " हज़ार")
        if remainder:
            parts.append(under_thousand(remainder))
        return " ".join(parts)

    if value < 100:
        return under_hundred(value)
    crores, remainder = divmod(value, 10_000_000)
    parts: list[str] = []
    if crores:
        parts.append(under_hundred(crores) + " करोड़")
    lakhs, remainder = divmod(remainder, 100_000)
    if lakhs:
        parts.append(under_hundred(lakhs) + " लाख")
    if remainder:
        parts.append(under_lakh(remainder))
    if value < 100_000:
        return under_lakh(value)
    return " ".join(parts)


def _thai_counting(value: int) -> str:
    if value < 0:
        return str(value)
    digits = ("ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า")
    if value == 0:
        return digits[0]

    def under_million(number: int) -> str:
        if number >= 1_000_000:
            quotient, remainder = divmod(number, 1_000_000)
            return under_million(quotient) + "ล้าน" + (under_million(remainder) if remainder else "")
        parts: list[str] = []
        for divisor, unit in ((100_000, "แสน"), (10_000, "หมื่น"), (1_000, "พัน"), (100, "ร้อย")):
            quotient, number = divmod(number, divisor)
            if quotient:
                parts.append(("หนึ่ง" if quotient == 1 else under_million(quotient)) + unit)
        quotient, number = divmod(number, 10)
        if quotient:
            parts.append("สิบ" if quotient == 1 else "ยี่สิบ" if quotient == 2 else digits[quotient] + "สิบ")
        if number:
            parts.append("เอ็ด" if parts and number == 1 else digits[number])
        return "".join(parts)

    return under_million(value)


def _vietnamese_counting(value: int) -> str:
    if value < 0:
        return str(value)
    if value > _MAX_WORD_VALUE:
        return ""
    digits = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")

    def under_hundred(number: int) -> str:
        if number < 10:
            return digits[number]
        tens, ones = divmod(number, 10)
        prefix = "mười" if tens == 1 else digits[tens] + " mươi"
        if not ones:
            return prefix
        if ones == 1 and tens > 1:
            return prefix + " mốt"
        if ones == 4 and tens > 1:
            return prefix + " tư"
        if ones == 5 and tens:
            return prefix + " lăm"
        return prefix + " " + digits[ones]

    def under_thousand(number: int) -> str:
        hundreds, remainder = divmod(number, 100)
        if not hundreds:
            return under_hundred(remainder)
        prefix = digits[hundreds] + " trăm"
        if not remainder:
            return prefix
        if remainder < 10:
            return prefix + " lẻ " + digits[remainder]
        return prefix + " " + under_hundred(remainder)

    def under_billion(number: int) -> str:
        millions, remainder = divmod(number, 1_000_000)
        if millions:
            result = under_thousand(millions) + " triệu"
            if remainder:
                result += " " + under_billion(remainder)
            return result
        thousands, remainder = divmod(number, 1000)
        if thousands:
            result = under_thousand(thousands) + " nghìn"
            if remainder:
                result += " " + under_thousand(remainder)
            return result
        return under_thousand(number)

    return under_billion(value)
