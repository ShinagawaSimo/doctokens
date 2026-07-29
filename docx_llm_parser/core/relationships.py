"""OPC relationship 只读索引。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable

from .models import RelationshipRecord


@dataclass(frozen=True)
class RelationshipIndex:
    """按 source part、relationship id 和类型索引 OPC relationship。"""

    records: tuple[RelationshipRecord, ...]
    _by_source_id: dict[tuple[str, str], RelationshipRecord]
    _by_source: dict[str, tuple[RelationshipRecord, ...]]
    _by_type: dict[str, tuple[RelationshipRecord, ...]]
    _by_source_type: dict[tuple[str, str], tuple[RelationshipRecord, ...]]

    @classmethod
    def from_records(cls, records: Iterable[RelationshipRecord]) -> "RelationshipIndex":
        """一次性构建多路索引，后续解析阶段只读复用。"""
        rows = tuple(records)
        by_source_id: dict[tuple[str, str], RelationshipRecord] = {}
        by_source: dict[str, list[RelationshipRecord]] = defaultdict(list)
        by_type: dict[str, list[RelationshipRecord]] = defaultdict(list)
        by_source_type: dict[tuple[str, str], list[RelationshipRecord]] = defaultdict(list)

        for rel in rows:
            # Relationship 的 source/id/type 是 OPC 解析阶段生成的内部契约字段。
            by_source_id[(rel.source_part, rel.id)] = rel
            by_source[rel.source_part].append(rel)
            by_type[rel.type].append(rel)
            by_source_type[(rel.source_part, rel.type)].append(rel)

        return cls(
            records=rows,
            _by_source_id=by_source_id,
            _by_source={key: tuple(value) for key, value in by_source.items()},
            _by_type={key: tuple(value) for key, value in by_type.items()},
            _by_source_type={key: tuple(value) for key, value in by_source_type.items()},
        )

    def get(self, source_part: str, rel_id: str) -> RelationshipRecord | None:
        """按 source part 和 rId 查找 relationship。"""
        return self._by_source_id.get((source_part, rel_id))

    def require(self, source_part: str, rel_id: str) -> RelationshipRecord:
        """按内部契约读取必然存在的 relationship。"""
        return self._by_source_id[(source_part, rel_id)]

    def by_source(self, source_part: str) -> tuple[RelationshipRecord, ...]:
        """返回某个 source part 声明的所有 relationship。"""
        return self._by_source.get(source_part, ())

    def by_type(
        self, rel_type: str, source_part: str | None = None
    ) -> tuple[RelationshipRecord, ...]:
        """按 relationship 类型读取；可选限制 source part。"""
        if source_part is not None:
            return self._by_source_type.get((source_part, rel_type), ())
        return self._by_type.get(rel_type, ())

    def to_debug_list(self) -> list[dict]:
        """输出 debug JSON 可序列化结构。"""
        return [asdict(item) for item in self.records]
