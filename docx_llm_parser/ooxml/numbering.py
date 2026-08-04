"""解析 Word 自动编号，并生成段落可见编号文本。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from types import MappingProxyType
from xml.etree import ElementTree as ET

from ..core.constants import attr, child_elements, first_child
from ..core.models import NumberingLabel, ParseWarning
from ..core.package import PackageReader


@dataclass(frozen=True)
class NumberingLevel:
    """单个编号层级的显示规则。"""

    numbering_level: int
    start: int = 1
    number_format: str = "decimal"
    level_text: str | None = None
    suffix: str = "tab"
    paragraph_style_id: str | None = None


@dataclass(frozen=True)
class NumberingInstance:
    """一个 numId 对应的实际编号实例。"""

    numbering_id: str
    abstract_num_id: str
    level_overrides: Mapping[int, NumberingLevel] = field(default_factory=dict)
    start_overrides: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "level_overrides", MappingProxyType(dict(self.level_overrides)))
        object.__setattr__(self, "start_overrides", MappingProxyType(dict(self.start_overrides)))


class NumberingMap:
    """只读编号定义索引；运行时计数由 NumberingState 单独维护。"""

    def __init__(
        self,
        abstract_levels: dict[str, dict[int, NumberingLevel]],
        instances: dict[str, NumberingInstance],
        warnings: list[ParseWarning],
    ) -> None:
        self.abstract_levels: Mapping[str, Mapping[int, NumberingLevel]] = MappingProxyType(
            {key: MappingProxyType(dict(value)) for key, value in abstract_levels.items()}
        )
        self.instances: Mapping[str, NumberingInstance] = MappingProxyType(dict(instances))
        self.warnings = warnings

    def level_for(self, num_id: str, numbering_level: int) -> NumberingLevel | None:
        """按 numId/ilvl 找到最终生效的层级规则。"""
        instance = self.instances.get(num_id)
        if instance is None:
            return None
        if numbering_level in instance.level_overrides:
            # lvlOverride 中的完整 lvl 定义优先于 abstractNum。
            return instance.level_overrides[numbering_level]
        base = self.abstract_levels.get(instance.abstract_num_id, {}).get(numbering_level)
        if base is None:
            return None
        if numbering_level in instance.start_overrides:
            # startOverride 只改起始值，其余格式继承 abstractNum。
            return replace(base, start=instance.start_overrides[numbering_level])
        return base

    def to_debug_dict(self) -> dict[str, object]:
        """输出 debug 用编号定义，最终 XML 不直接暴露这些字段。"""
        return {
            "abstractNums": {
                abstract_id: {
                    str(numbering_level): asdict(level)
                    for numbering_level, level in sorted(levels.items())
                }
                for abstract_id, levels in sorted(self.abstract_levels.items())
            },
            "nums": {
                numbering_id: {
                    "numId": instance.numbering_id,
                    "abstractNumId": instance.abstract_num_id,
                    "levelOverrides": {
                        str(numbering_level): asdict(level)
                        for numbering_level, level in sorted(instance.level_overrides.items())
                    },
                    "startOverrides": {
                        str(numbering_level): start
                        for numbering_level, start in sorted(instance.start_overrides.items())
                    },
                }
                for numbering_id, instance in sorted(self.instances.items())
            },
        }


class NumberingState:
    """维护单篇文档的编号计数，避免并发任务共享状态。"""

    def __init__(self, numbering: NumberingMap, warnings: list[ParseWarning]) -> None:
        self.numbering = numbering
        self.warnings = warnings
        self._counters: dict[str, dict[int, int]] = {}
        self._warned_formats: set[str] = set()

    def advance(
        self,
        num_id: str,
        numbering_level: int,
        *,
        part: str | None = None,
        block_id: str | None = None,
    ) -> NumberingLabel | None:
        """推进指定编号序列，并返回应该插入段落开头的可见编号。"""
        level = self.numbering.level_for(num_id, numbering_level)
        if level is None:
            self.warnings.append(
                ParseWarning(
                    code="NUMBERING_LEVEL_MISSING",
                    message=(
                        f"Missing numbering level for numId={num_id}, "
                        f"numbering_level={numbering_level}"
                    ),
                    locator=":".join(filter(None, [part, block_id])),
                )
            )
            return None

        counters = self._counters.setdefault(num_id, {})
        if numbering_level not in counters:
            counters[numbering_level] = level.start
        else:
            counters[numbering_level] += 1
        for existing_numbering_level in list(counters):
            if existing_numbering_level > numbering_level:
                del counters[existing_numbering_level]

        label = self._render_label(num_id, numbering_level, counters)
        visible_text = label + self._suffix_text(level.suffix)
        return {
            "numId": num_id,
            "level": numbering_level,
            "label": label,
            "text": visible_text,
            "format": level.number_format,
            "template": level.level_text,
            "suffix": level.suffix,
            "counter": counters[numbering_level],
        }

    def _render_label(self, num_id: str, numbering_level: int, counters: dict[int, int]) -> str:
        """把 lvlText 中的 %1、%2 等占位符替换成真实编号。"""
        current_level = self.numbering.level_for(num_id, numbering_level)
        if current_level is None:
            return ""
        template = current_level.level_text
        if not template:
            # bullet 通常会把符号直接放在 lvlText；缺失时给一个轻量符号。
            return (
                "•"
                if current_level.number_format == "bullet"
                else self._format_number(
                    counters.get(numbering_level, current_level.start), current_level.number_format
                )
            )

        def replace_match(match: re.Match[str]) -> str:
            ref_numbering_level = int(match.group(1)) - 1
            ref_level = self.numbering.level_for(num_id, ref_numbering_level) or current_level
            value = counters.get(ref_numbering_level, ref_level.start)
            return self._format_number(value, ref_level.number_format)

        return re.sub(r"%([1-9])", replace_match, template)

    def _format_number(self, value: int, number_format: str) -> str:
        """按 OOXML numFmt 把整数转换成可见编号文本。"""
        if number_format in {"decimal", "ordinal"}:
            return str(value)
        if number_format == "decimalZero":
            return f"{value:02d}"
        if number_format == "upperLetter":
            return self._alpha(value).upper()
        if number_format == "lowerLetter":
            return self._alpha(value).lower()
        if number_format == "upperRoman":
            return self._roman(value).upper()
        if number_format == "lowerRoman":
            return self._roman(value).lower()
        if number_format in {
            "chineseCounting",
            "chineseCountingThousand",
            "ideographDigital",
            "japaneseCounting",
            "taiwaneseCounting",
        }:
            return self._chinese_counting(value)
        if number_format == "bullet":
            return "•"

        if number_format not in self._warned_formats:
            # 未覆盖格式不阻断解析，先用十进制兜底并在 debug 中暴露风险。
            self._warned_formats.add(number_format)
            self.warnings.append(
                ParseWarning(
                    code="UNSUPPORTED_NUMBER_FORMAT",
                    message=(
                        f"Unsupported numbering format {number_format!r}; decimal fallback is used."
                    ),
                    locator="word/numbering.xml",
                )
            )
        return str(value)

    @staticmethod
    def _suffix_text(suffix: str) -> str:
        """把 Word 编号后缀转换成最终文本中的轻量空白。"""
        if suffix == "nothing":
            return ""
        if suffix == "space":
            return " "
        return "\t"

    @staticmethod
    def _alpha(value: int) -> str:
        """生成 A/B/.../AA 风格字母编号。"""
        value = max(1, value)
        chars: list[str] = []
        while value:
            value -= 1
            chars.append(chr(ord("A") + (value % 26)))
            value //= 26
        return "".join(reversed(chars))

    @staticmethod
    def _roman(value: int) -> str:
        """生成罗马数字；超大值退化为十进制，避免输出错误长串。"""
        if value <= 0 or value > 3999:
            return str(value)
        pairs = [
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I"),
        ]
        result: list[str] = []
        for amount, glyph in pairs:
            while value >= amount:
                result.append(glyph)
                value -= amount
        return "".join(result)

    @staticmethod
    def _chinese_counting(value: int) -> str:
        """生成简体中文计数，覆盖常见章节/条目编号。"""
        if value <= 0:
            return str(value)
        digits = "零一二三四五六七八九"
        if value < 10:
            return digits[value]
        if value < 100:
            tens, ones = divmod(value, 10)
            prefix = "" if tens == 1 else digits[tens]
            return prefix + "十" + (digits[ones] if ones else "")
        units = [(1000, "千"), (100, "百"), (10, "十")]
        remaining = value
        parts: list[str] = []
        zero_pending = False
        for amount, unit in units:
            digit, remaining = divmod(remaining, amount)
            if digit:
                if zero_pending:
                    parts.append("零")
                    zero_pending = False
                parts.append(digits[digit] + unit)
            elif parts and remaining:
                zero_pending = True
        if remaining:
            if zero_pending:
                parts.append("零")
            parts.append(digits[remaining])
        return "".join(parts)


class NumberingParser:
    """读取 word/numbering.xml 并构建编号定义。"""

    def __init__(self, package: PackageReader, warnings: list[ParseWarning]) -> None:
        self.package = package
        self.warnings = warnings

    def parse(self) -> NumberingMap:
        """解析编号 part；缺失时返回空编号表。"""
        if not self.package.exists("word/numbering.xml"):
            return NumberingMap({}, {}, self.warnings)

        with self.package.open_entry("word/numbering.xml") as stream:
            root = ET.parse(stream).getroot()

        abstract_levels: dict[str, dict[int, NumberingLevel]] = {}
        for abstract_num in child_elements(root, "w", "abstractNum"):
            abstract_id = attr(abstract_num, "w", "abstractNumId")
            if not abstract_id:
                continue
            levels: dict[int, NumberingLevel] = {}
            for lvl in child_elements(abstract_num, "w", "lvl"):
                level = self._parse_level(lvl)
                if level is not None:
                    levels[level.numbering_level] = level
            abstract_levels[abstract_id] = levels

        instances: dict[str, NumberingInstance] = {}
        for num in child_elements(root, "w", "num"):
            num_id = attr(num, "w", "numId")
            abstract_id = self._child_attr(num, "abstractNumId", "val")
            if not num_id or not abstract_id:
                continue
            level_overrides: dict[int, NumberingLevel] = {}
            start_overrides: dict[int, int] = {}
            for override in child_elements(num, "w", "lvlOverride"):
                override_level_index = self._parse_int(attr(override, "w", "ilvl"))
                if override_level_index is None:
                    override_level_index = 0
                start = self._parse_int(self._child_attr(override, "startOverride", "val"))
                if start is not None:
                    start_overrides[override_level_index] = start
                override_level = self._parse_level(first_child(override, "w", "lvl"))
                if override_level is not None:
                    level_overrides[override_level_index] = override_level
            instances[num_id] = NumberingInstance(
                numbering_id=num_id,
                abstract_num_id=abstract_id,
                level_overrides=level_overrides,
                start_overrides=start_overrides,
            )

        return NumberingMap(abstract_levels, instances, self.warnings)

    def _parse_level(self, lvl: ET.Element | None) -> NumberingLevel | None:
        """解析一个 w:lvl 节点。"""
        if lvl is None:
            return None
        level_value = self._parse_int(attr(lvl, "w", "ilvl"))
        if level_value is None:
            level_value = 0
        start = self._parse_int(self._child_attr(lvl, "start", "val"), 1) or 1
        number_format = self._child_attr(lvl, "numFmt", "val") or "decimal"
        level_text = self._child_attr(lvl, "lvlText", "val")
        suffix = self._child_attr(lvl, "suff", "val") or "tab"
        paragraph_style_id = self._child_attr(lvl, "pStyle", "val")
        return NumberingLevel(
            numbering_level=level_value,
            start=start,
            number_format=number_format,
            level_text=level_text,
            suffix=suffix,
            paragraph_style_id=paragraph_style_id,
        )

    @staticmethod
    def _child_attr(node: ET.Element, child_name: str, attr_name: str) -> str | None:
        """读取直接子节点上的 w 属性，子节点缺失时返回 None。"""
        child = first_child(node, "w", child_name)
        return attr(child, "w", attr_name) if child is not None else None

    @staticmethod
    def _parse_int(value: str | None, default: int | None = None) -> int | None:
        """安全读取 OOXML 整数字段。"""
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
