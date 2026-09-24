# Resource operations

[PPTX](../README.md) / Resource operations

Embedded resources are accessed through an open PPTX session.

## Fields

### `kind`

- **Output**
  - Bytes or explanatory ParseResult.

- **Source**
  - Resource directory.

- **IR**
  - `str`

- **Parsing**
  - Binary image/media. Explanatory chart/smartart/table, singular only. External binary → ValueError; missing ID → KeyError.

### `resource_id`

- **Output**
  - Resource selector.

- **Source**
  - ResourceDescriptor.id.

- **IR**
  - `str`

- **Parsing**
  - Table ID is tableN, distinct from its slide-local sN XML ID.

### `rows`

- **Output**
  - Table source rows.

- **Source**
  - Call argument.

- **IR**
  - `str | None`

- **Parsing**
  - N or N-M, positive decimal ordinals; inclusive. Reject reversed ranges and any bound outside table. None → all.

### `columns`

- **Output**
  - Table output columns.

- **Source**
  - Call argument.

- **IR**
  - `list[int] | None`

- **Parsing**
  - Zero-based nonnegative integers, excluding bool. Preserve request order and duplicates; out-of-row positions omitted.

### `aggregate`

- **Output**
  - Additional table aggregate record.

- **Source**
  - Call argument.

- **IR**
  - `str | None`

- **Parsing**
  - Exact sum/count/avg/min/max. Apply to selected source rows before column filtering; float(cell) failures ignored. count counts numeric values; no numeric values → 0.

### `aggregate_column`

- **Output**
  - Aggregate source column.

- **Source**
  - Call argument.

- **IR**
  - `int | None`

- **Parsing**
  - Zero-based nonnegative non-bool int; must accompany aggregate and is required with it.

### `text`

- **Output**
  - Resource result text.

- **Source**
  - Object IR.

- **IR**
  - `ParseResult.text`

- **Parsing**
  - syntax_version=legacy-markup/0; media_type=text/plain; density=semantic. Chart uses comma-joined cached arrays; SmartArt uses node/link records; table includes selected rows plus optional aggregate. Exact constructors below define escaping and boundaries.


## Source references

- [PptxReadSession.render_resource](../../../packages/pptx_llm_parser/src/pptx_llm_parser/api.py#L229)
- [_render_chart](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/resources.py#L61)
- [_render_smartart](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/resources.py#L105)
- [_render_table](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/resources.py#L129)
