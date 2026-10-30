# Array formulas and spills

[XLSX](../README.md) / Array formulas and spills

Classic CSE array declarations and saved dynamic-array relationships are distinct.
The parser reads saved formula/cache data; it never evaluates a formula.

## Fields

### `dynamicArray`

- **Output**
  - Internal eligibility marker; the saved spill range/recipient references
    carry the public relationship.
- **OOXML**
  - Cell `s:c/@cm`, metadataTypes, cellMetadata and futureMetadata in the
    workbook's sheetMetadata relationship target (or conventional
    `xl/metadata.xml` when present without that relationship).
  - Dynamic properties use
    `http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray`.
- **IR**
  - `Cell.dynamicArray: bool`; `DynamicArrayCatalog`.
- **Parsing**
  - Treat cm as a one-based cellMetadata/bk index; absent or zero means no
    associated cell metadata. Each bk/rc/@t is a one-based metadataType index.
    Only a type named XLDAPR participates. Its rc/@v is a zero-based bk index
    inside futureMetadata[@name="XLDAPR"].
  - Read that record's dynamicArrayProperties/@fDynamic. The saved true
    forms 1/true establish dynamic semantics; 0/false do not.
    fCollapsed describes a different state and is not a dynamic flag.
  - Require a saved `f[@t="array"]` and a valid declared range before
    producing a spill association. An array function name, prefix, cached
    error, or aca attribute does not establish dynamic semantics.
  - Invalid indices, type references or dynamic flags emit
    DYNAMIC_ARRAY_METADATA_UNRESOLVED and preserve the ordinary saved array
    formula and cell values. Missing/invalid optional metadata parts use
    [catalog diagnostics](../workbook/catalog-diagnostics.md).

### `aca`

- **Output**
  - No reading attribute.
- **OOXML**
  - s:f/@aca: array calculation strategy.
- **Parsing**
  - aca is not a dynamic-array marker. For example, a traditional array
    `ROW(A1:A2)` with aca=1 retains formula-type=array and formula-range,
    without spill-range or spill-from.

### `spillRange`

- **Output**
  - Source cell/@spill-range in structural/semantic output.
- **OOXML**
  - Dynamic array formula's saved f/@ref.
- **IR**
  - `Cell.spillRange: str`.
- **Parsing**
  - Validate ordered A1 endpoints within A1:XFD1048576 and require the
    source to be the top-left cell. A single-cell result creates no
    additional spill-range attribute. Invalid ranges emit
    DYNAMIC_ARRAY_RANGE_INVALID; no size is guessed.
  - Collect source declarations while scanning even if their cells lie
    outside a requested range. Do not create absent cells or expand the
    requested output window.

### `spillFrom`

- **Output**
  - Recipient cell/@spill-from in structural/semantic output.
- **OOXML**
  - Retained saved cells inside a validated dynamic range.
- **IR**
  - `Cell.spillFrom: str`.
- **Parsing**
  - Set the source A1 reference only on recipients with neither their own
    formula nor shared-formula index. Preserve saved values and source
    coordinates. Iterate retained cells rather than allocating/iterating
    every coordinate in a possibly enormous declared rectangle.
  - Example: saved A1:A2 dynamic result 1,2 yields spill-range=A1:A2 on
    A1 and spill-from=A1 on A2. Reading only A2 still retains spill-from=A1.
    Plain output retains its existing value-only formula policy.
