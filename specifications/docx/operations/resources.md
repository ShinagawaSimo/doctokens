# Resource operations

[DOCX](../README.md) / Resource operations

Session binary reads and explanatory renderings have distinct result types.

## Fields

### `kind`

- **Output**
  - read_resource bytes or render_resource ParseResult.

- **Source**
  - Resource directory.

- **IR**
  - `str`

- **Parsing**
  - Binary: image. Explanatory: chart/smartart/table, singular only; invalid/plural → ValueError. Unknown resource → KeyError. External image bytes → ValueError.

### `resource_id`

- **Output**
  - Resource selector.

- **Source**
  - ResourceDescriptor.id.

- **IR**
  - `str`

- **Parsing**
  - Exact matching. Group logical table segments throughout the retained block
    tree, including nested cells and text-box stories in body and ancillary content.
    Their ids use the same document-level allocator and have standalone directory entries.

### `rows`

- **Output**
  - Table row slice.

- **Source**
  - Call argument.

- **IR**
  - `str | None`

- **Parsing**
  - DOCX requires start-end; start>=1; int conversion and Python slicing. End beyond table is clipped. Applied after column filter; not applied when aggregate is supplied.

### `columns`

- **Output**
  - Table column selection.

- **Source**
  - Call argument.

- **IR**
  - `list[str] | None`

- **Parsing**
  - Exact text match against first row; first matching occurrence per name; unmatched names ignored; retained positions sorted to source order.

### `aggregate`

- **Output**
  - Table numeric aggregation.

- **Source**
  - Call argument.

- **IR**
  - `str | None`

- **Parsing**
  - Lowercase sum/count/avg/min/max. Uses full table rows after first row, ignoring rows/columns options. Parse stripped nonempty float text; ignore failures. Empty numeric input → 0; count counts numeric values.

### `aggregate_column`

- **Output**
  - Aggregate input label.

- **Source**
  - Call argument.

- **IR**
  - `str | None`

- **Parsing**
  - First exact first-row cell text match; missing label → ValueError when table has rows.

### `text`

- **Output**
  - Resource result text.

- **Source**
  - Retained object IR.

- **IR**
  - `ParseResult.text`

- **Parsing**
  - `syntax_version=doctokens-xml/1.0`, `media_type=application/xml`, `density=semantic`. Complete `<document density="semantic" format="docx"><resources>OBJECT</resources></document>`.
  - Tables use closed `table/tr/td` elements; aggregate output uses `table/aggregate` with `op`, `column`, and numeric text. Charts retain series and point records; SmartArt retains node and link records. XML attributes and text are escaped by the shared serializer.
