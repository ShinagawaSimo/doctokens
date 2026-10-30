# Table cells

[PPTX](../README.md) / Table cells

DTX omits continuation cells and retains origin spans.

## Fields

### `text`

- **Output**
  - `td` inline content. Multiple retained source paragraphs use child `p`
    elements; a single paragraph stays directly inside `td`.

- **OOXML**
  - a:tc/a:txBody.

- **IR**
  - `TableCell.text: str`

- **Parsing**
  - Use the same DrawingML paragraph/run reader as slide text. The saved text
    remains the plain TSV and data-resource value. List counters are scoped
    to the cell; source paragraphs are separate search units.

### `paragraphs`

- **Output**
  - Both XML densities preserve hyperlinks and equations; semantic additionally
    preserves [character formats](../text/emphasis.md). Nonzero paragraph
    list levels remain on child p elements in multi-paragraph cells.
- **OOXML**
  - a:tc/a:txBody/a:p, including a:pPr/a:defRPr, a:r, a:fld, and native math.
- **IR**
  - `TableCell.paragraphs: list[Paragraph]`.
- **Parsing**
  - Read cell txBody/lstStyle defaults, then paragraph defaults and direct run
    properties with the slide's effective theme/color map and hyperlinks.
    Normalize internal slide links through the existing navigation map.
  - Merge origins and continuation suppression are independent of rich text.
    Body preview limits and the text-only rectangular table-resource
    slicing/aggregation contract remain as defined in [tables](table.md) and
    [resources](../operations/resources.md). Table-style font synthesis is
    outside this direct/inherited text-body reading scope.

### `colSpan`

- **Output**
  - `td/@colspan` if !=1.

- **OOXML**
  - a:tc/@gridSpan.

- **IR**
  - `int`

- **Parsing**
  - Parse integer default 1; store only >1. Without explicit span, add contiguous hMerge cells to prior non-hMerge anchor.

### `rowSpan`

- **Output**
  - `td/@rowspan` if !=1.

- **OOXML**
  - a:tc/@rowSpan.

- **IR**
  - `int`

- **Parsing**
  - Parse integer default 1; store only >1. Without explicit origin span, vMerge cell extends nearest preceding non-vMerge cell at same array column.

### `hMerge`

- **Output**
  - Suppresses DTX td.

- **OOXML**
  - a:tc/@hMerge.

- **IR**
  - `bool`

- **Parsing**
  - DrawingML bool; retained only true.

### `vMerge`

- **Output**
  - Suppresses DTX td.

- **OOXML**
  - a:tc/@vMerge.

- **IR**
  - `bool`

- **Parsing**
  - DrawingML bool; retained only true.
