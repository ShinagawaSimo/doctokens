# Numbering instances

[DOCX](../README.md) / Numbering instances

A `w:num` instance selects an abstract definition and owns an independent set of paragraph counters.

## Processing

1. If `word/numbering.xml` is absent, return empty definition maps without a warning.
2. Read picture-bullet relationships, abstract levels, and instances.
3. For `(numId, level)`, resolve the instance level override, then its linked numbering instance, then its abstract base level.
4. Apply the instance start override to the resolved level. An unresolved level returns `None`; paragraph numbering reports `NUMBERING_LEVEL_MISSING`.

## Fields

### `numbering_id`

- **Output**
  - Key for counter state.

- **OOXML**
  - `w:num/@w:numId`

- **IR**
  - `NumberingInstance.numbering_id: str`

- **Parsing**
  - Retain a nonempty string. Later instances with the same ID replace earlier ones.

- **Absence and defaults**
  - Missing or empty: skip the instance.

### `abstract_num_id`

- **Output**
  - Abstract level lookup.

- **OOXML**
  - `w:num/w:abstractNumId/@w:val`

- **IR**
  - `NumberingInstance.abstract_num_id: str`

- **Parsing**
  - Retain a nonempty string. The selected `w:abstractNum` must have a nonempty `@w:abstractNumId`; later duplicate abstract IDs and level indices replace earlier definitions.

- **Absence and defaults**
  - Missing or empty: skip the instance.

### `level_overrides`

- **Output**
  - Level definitions that take precedence over the base definition.

- **OOXML**
  - `w:num/w:lvlOverride/w:lvl`

- **IR**
  - `NumberingInstance.level_overrides: Mapping[int, NumberingLevel]`

- **Parsing**
  - Parse [level fields](numbering-level.md), then set `numbering_level` to the override index and `restart_level=None`. Override index is `int(@w:ilvl)`, defaulting to `0` on absence or failure. Later definitions of an index replace earlier ones.

- **Absence and defaults**
  - Missing nested level: no override.

### `start_overrides`

- **Output**
  - Initial counters overriding any resolved level.

- **OOXML**
  - `w:num/w:lvlOverride/w:startOverride/@w:val`

- **IR**
  - `NumberingInstance.start_overrides: Mapping[int, int]`

- **Parsing**
  - Store successfully parsed integers under the override index. Apply with `replace(level, start=start)` after level resolution.

- **Absence and defaults**
  - Missing or invalid integer: omit.

### `style_link_num_ids`

- **Output**
  - Intermediate links between numbering instances.

- **OOXML**
  - `w:abstractNum/w:numStyleLink/@w:val` → numbering style → `numId`

- **IR**
  - `NumberingMap.style_link_num_ids: Mapping[str, str]`

- **Parsing**
  - Retain the linked `numId` if found in the numbering-style map. Recursive resolution terminates on a repeated instance ID.

- **Absence and defaults**
  - Unresolved style: no link.


## Source references

- [NumberingParser](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/parser.py#L97)
- [NumberingMap._level_for](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/parser.py#L42)
- [NumberingInstance](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/models.py#L32)
