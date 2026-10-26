"""Format east asian."""

from __future__ import annotations

from typing import Protocol

from .format_sequences import _korean_unit_counting, _translate_digits, _unit_counting


class RangeWarning(Protocol):
    def __call__(self, value: int, number_format: str, *, display: str) -> str: ...


class EastAsianNumberRenderer:
    """East Asian unit-based numbering with the caller's shared diagnostics."""

    def __init__(self, on_out_of_range: RangeWarning) -> None:
        self._out_of_range = on_out_of_range

    def _chinese_counting_thousand(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "chineseCountingThousand", display="")
        if value < 10_000:
            return _unit_counting(value, "〇一二三四五六七八九", "十百千", zero="〇")
        high, low = divmod(value, 10_000)
        result = (
            _unit_counting(
                high,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_ten=value < 100_000,
            )
            + "万"
        )
        if low:
            # Word renders the zero between the ten-thousands group and a
            # lower group below one thousand (for example, 一万〇五十).
            if low < 1_000:
                result += "〇"
            result += _unit_counting(low, "〇一二三四五六七八九", "十百千", zero="〇")
        return result

    def _taiwanese_counting(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value < 100:
            return _unit_counting(value, "○一二三四五六七八九", "十百千", zero="○")
        return _translate_digits(value, digits="○一二三四五六七八九")

    def _taiwanese_counting_thousand(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "taiwaneseCountingThousand", display="")
        if value < 10_000:
            return _unit_counting(value, "零一二三四五六七八九", "十百千", zero="零")
        high, low = divmod(value, 10_000)
        result = (
            _unit_counting(
                high,
                "零一二三四五六七八九",
                "十百千",
                zero="零",
                omit_one_ten=value < 100_000,
            )
            + "萬"
        )
        if low:
            if low < 1_000 and value % 10 != 0:
                result += "零"
            result += _unit_counting(low, "零一二三四五六七八九", "十百千", zero="零")
        return result

    def _chinese_legal_simplified(self, value: int) -> str:
        return self._legal_counting(
            value,
            digits="零壹贰叁肆伍陆柒捌玖",
            units="拾佰仟",
            large_unit="萬",
            format_name="chineseLegalSimplified",
        )

    def _ideograph_legal_traditional(self, value: int) -> str:
        return self._legal_counting(
            value,
            digits="零壹貳叁肆伍陸柒捌玖",
            units="拾佰仟",
            large_unit="萬",
            format_name="ideographLegalTraditional",
        )

    def _legal_counting(
        self,
        value: int,
        *,
        digits: str,
        units: str,
        large_unit: str,
        format_name: str,
    ) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, format_name, display="")
        if value < 10_000:
            return _unit_counting(value, digits, units, zero=digits[0], omit_one_ten=False)
        high, low = divmod(value, 10_000)
        result = _unit_counting(high, digits, units, zero=digits[0], omit_one_ten=False) + large_unit
        if low:
            if low < 1_000:
                result += digits[0]
            result += _unit_counting(low, digits, units, zero=digits[0], omit_one_ten=False)
        return result

    def _japanese_counting(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "japaneseCounting", display="")
        if value < 10_000:
            return _unit_counting(
                value,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_units=True,
                insert_zero=False,
            )
        high, low = divmod(value, 10_000)
        result = (
            _unit_counting(
                high,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_units=True,
                insert_zero=False,
            )
            + "万"
        )
        return (
            result
            if not low
            else result
            + _unit_counting(
                low,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_units=True,
                insert_zero=False,
            )
        )

    def _japanese_legal(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value >= 100_000_000:
            high, low = divmod(value, 100_000_000)
            result = (
                _unit_counting(
                    high,
                    "〇壱弐参四伍六七八九",
                    "拾百阡",
                    zero="〇",
                    omit_one_ten=False,
                )
                + "億"
            )
            if low:
                result += self._japanese_legal_under_100m(low)
            return result
        return self._japanese_legal_under_100m(value)

    def _japanese_legal_under_100m(self, value: int) -> str:
        if value < 10_000:
            return _unit_counting(value, "〇壱弐参四伍六七八九", "拾百阡", zero="〇", omit_one_ten=False, insert_zero=False)
        high, low = divmod(value, 10_000)
        result = (
            _unit_counting(
                high,
                "〇壱弐参四伍六七八九",
                "拾百阡",
                zero="〇",
                omit_one_ten=False,
            )
            + "萬"
        )
        if low:
            result += _unit_counting(
                low,
                "〇壱弐参四伍六七八九",
                "拾百阡",
                zero="〇",
                omit_one_ten=False,
                insert_zero=False,
            )
        return result

    def _korean_counting(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "koreanCounting", display="")
        return _korean_unit_counting(value)

    def _korean_legal(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 9_999_999:
            return self._out_of_range(value, "koreanLegal", display="")
        if value < 100:
            small = {
                0: "영",
                1: "하나",
                2: "둘",
                3: "셋",
                4: "넷",
                5: "다섯",
                6: "여섯",
                7: "일곱",
                8: "여덟",
                9: "아홉",
                10: "열",
                20: "스물",
                30: "서른",
                40: "마흔",
                50: "쉰",
                60: "예순",
                70: "일흔",
                80: "여든",
                90: "아흔",
            }
            tens, ones = divmod(value, 10)
            if tens == 0 or ones == 0:
                return small[value]
            return small[tens * 10] + small[ones]
        return _korean_unit_counting(value)
