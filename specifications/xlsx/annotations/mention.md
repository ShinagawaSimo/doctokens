# Comment mentions

[XLSX](../README.md) / Comment mentions

Mention offsets are retained without editing comment text.

## Fields

### `person`

- **Output**
  - Internal display name.

- **OOXML**
  - mention/@personId → people catalog.

- **IR**
  - `AnnotationMention.person: str`

- **Parsing**
  - Skip mention if person cannot resolve.

### `start`

- **Output**
  - Internal offset.

- **OOXML**
  - mention/@startIndex.

- **IR**
  - `int`

- **Parsing**
  - Parse integer; missing/invalid omitted; no bounds validation against comment text.

### `length`

- **Output**
  - Internal length.

- **OOXML**
  - mention/@length.

- **IR**
  - `int`

- **Parsing**
  - Parse integer; missing/invalid omitted.


## Source references

- [_threaded_mentions](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L309)
