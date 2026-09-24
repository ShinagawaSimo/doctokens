# ResourceDescriptor

[COMMON](README.md) / ResourceDescriptor

A resource descriptor identifies data available to a session. Presence in the directory does not imply a full main-text representation.

## Fields

### `id`

- **Output**
  - Resource lookup identifier.

- **OOXML**
  - Format-specific discovery order.

- **IR**
  - `ResourceDescriptor.id: str`

- **Parsing**
  - Stable for the same input and plan, scoped to one parse.

### `kind`

- **Output**
  - `image`, `media`, `chart`, `smartart`, `table`, or `pivot_table`, as supported by the format.

- **OOXML**
  - Relationship/parsed object class.

- **IR**
  - `ResourceDescriptor.kind: str`

- **Parsing**
  - A descriptor kind does not guarantee both binary and explanatory reading support.

### `source`

- **Output**
  - `embedded` or `external`.

- **OOXML**
  - Relationship TargetMode or format descriptor construction.

- **IR**
  - `ResourceDescriptor.source: ResourceSource`

- **Parsing**
  - Only supported embedded parts can yield binary bytes.

### `locator`

- **Output**
  - Source position.

- **OOXML**
  - Part, table ID, or `sheet!cell`.

- **IR**
  - `ResourceDescriptor.locator: str`

- **Parsing**
  - XLSX drawings use `sheet!ref`; DOCX/PPTX assets prefer `zipPath`, then `href`, then ID.

### `content_type`

- **Output**
  - Media type or `None`.

- **OOXML**
  - `[Content_Types].xml` when supplied by the format adapter.

- **IR**
  - `ResourceDescriptor.content_type: str | None`

- **Parsing**
  - Copy available media type. XLSX drawing descriptors currently leave this unset.

- **Absence and defaults**
  - `None`.

### `part`

- **Output**
  - Package part or `None`.

- **OOXML**
  - Resolved embedded target.

- **IR**
  - `ResourceDescriptor.part: str | None`

- **Parsing**
  - Presence is a locator, not proof the bytes have been read. Table/pivot summaries can have no dedicated binary part.

- **Absence and defaults**
  - `None`.

### `external_target`

- **Output**
  - Target string or `None`.

- **OOXML**
  - Asset `href`.

- **IR**
  - `ResourceDescriptor.external_target: str | None`

- **Parsing**
  - DOCX/PPTX adapters copy asset `href`; interpret using `source`, because embedded asset hrefs can also populate this member.

- **Absence and defaults**
  - `None`.


## Source references

- [ResourceDescriptor](../../packages/ooxml_llm_core/src/ooxml_llm_core/models.py#L59)
- [_resource_descriptors](../../packages/docx_llm_parser/src/docx_llm_parser/api.py#L39)
- [_resource_descriptors](../../packages/pptx_llm_parser/src/pptx_llm_parser/api.py#L28)
- [_resource_descriptors](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L36)
