# Reports and diagnostics

[COMMON](README.md) / Reports and diagnostics

Diagnostics are returned separately from document content.

## Fields

### `format`

- **Output**
  - Report format: `docx`, `pptx`, `xlsx`.

- **IR**
  - `ParseReport.format: str`

- **Parsing**
  - Set by format parser.

### `schema_version`

- **Output**
  - `to_dict()["schemaVersion"]`; currently `1`.

- **IR**
  - `ParseReport.schema_version: int`

- **Parsing**
  - Report schema version, independent of DTX version.

### `manifest`

- **Output**
  - Counts and navigation overview.

- **OOXML**
  - Parsed IR.

- **IR**
  - `ParseReport.manifest: dict[str, object]`

- **Parsing**
  - Describe parsed scope before rendering; later window selection does not recalculate counts. See [DOCX](../docx/manifest.md), [PPTX](../pptx/manifest.md), and [XLSX](../xlsx/manifest.md).

### `warnings`

- **Output**
  - Ordered diagnostic sequence.

- **OOXML**
  - Encountered unsupported/malformed source.

- **IR**
  - `ParseReport.warnings: tuple[ParseWarning, ...]`

- **Parsing**
  - Preserve collection order. Different feature plans can encounter different diagnostics.

### `metrics`

- **Output**
  - Stage timings and counters.

- **IR**
  - `ParseReport.metrics: MetricsSnapshot`

- **Parsing**
  - Keys include `totalMs`, `parseTotalMs`, `stagesMs`, `counters` as produced by each parser. Timing is not deterministic content.

### `code`

- **Output**
  - Machine-readable category.

- **OOXML**
  - Condition described by the relevant format field.

- **IR**
  - `ParseWarning.code: str`

- **Parsing**
  - Use this member, not message wording, to classify a warning.

### `message`

- **Output**
  - Human-readable cause.

- **IR**
  - `ParseWarning.message: str`

- **Parsing**
  - May include source values or the underlying XML error; wording is not a stable program key.

### `locator`

- **Output**
  - Position associated with the warning.

- **OOXML**
  - Part or format-specific object/cell/reference.

- **IR**
  - `ParseWarning.locator: str | None`

- **Parsing**
  - DOCX commonly uses `part:block`; XLSX missing ancillary targets use `source_part#rId`. Exact conditions are specified on the affected entry.

- **Absence and defaults**
  - `None` if no location is supplied.


## Source references

- [ParseReport](../../packages/ooxml_llm_core/src/ooxml_llm_core/models.py#L88)
- [ParseWarning](../../packages/ooxml_llm_core/src/ooxml_llm_core/models.py#L47)
- [locator.py](../../packages/ooxml_llm_core/src/ooxml_llm_core/locator.py)
