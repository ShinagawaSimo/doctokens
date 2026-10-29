# Shared formulas

[XLSX](../README.md) / [Cells](cell.md) / Shared formulas

A shared formula group is scoped to one worksheet. In structural and semantic output, a selected dependent cell can use a master declaration outside the selected range. Only selected cells enter the grid; an outside master contributes its reference, range, shared index, and formula text to expansion.

## Fields

### `si`

- **Output**
  - No DTX attribute; identifies a shared group during parsing.
- **OOXML**
  - `s:c/s:f[@t="shared"]/@si`.
- **IR**
  - `Cell.si: str`; `SharedFormulaMaster.si: str`.
- **Parsing**
  - Present values, including `""`, are grouped by exact string within the worksheet. A shared formula without `@si` does not enter a group.
  - Up to two distinct master declarations are retained per group; a second distinct declaration establishes a conflict. Identical declarations are deduplicated.

### `shared_ref`

- **Output**
  - No DTX attribute; constrains which cells can receive an expanded formula.
- **OOXML**
  - `s:c/s:f[@t="shared"]/@ref` on a master declaration.
- **IR**
  - `Cell.shared_ref: str`; `SharedFormulaMaster.shared_ref: str`.
- **Parsing**
  - A present `@ref` makes the cell a master candidate, even when the value is empty. The range accepts one A1 cell or `A1:B2`, with one to three ASCII letters per column, positive rows, ascending bounds, and Excel limits of 16,384 columns and 1,048,576 rows.
  - The master's coordinate and every selected group member must be inside the range. A selected group containing no dependent cell needs no expansion.
- **Diagnostics**
  - `SHARED_FORMULA_INVALID` if a selected dependent has conflicting masters, an invalid range, or a member outside that range. The cached cell value and any source formula remain unchanged.

### `formula`

- **Output**
  - `cell/@formula` in structural and semantic DTX. Plain output uses the saved display value and does not collect shared-formula dependencies.
- **OOXML**
  - Master `s:f` text; dependent `s:f[@t="shared"]` may have no text. Saved `s:v` supplies the independent cached value.
- **IR**
  - `SharedFormulaMaster.formula: str`; `Cell.formula: str`.
- **Parsing**
  - For a dependent at `(column, row)`, subtract the master's coordinate and apply that offset to relative A1 components in the master formula. `$`-anchored components and double-quoted literals are unchanged. A sheet qualifier is preserved, including quotes and escaped apostrophes; its relative cell coordinates still move. For example, copying `Source!B2` down one row yields `Source!B3`; `'Source A'!$B2` becomes `'Source A'!$B3`.
  - The [reference translator](../../../packages/doctokens_excel/src/doctokens_excel/xlsx/parsing/modules/worksheets/formula_refs.py) recognizes cells/ranges, entire-column ranges (`A:A`, `$A:C`), and entire-row ranges (`1:1`, `$1:3`), including whitespace around a range colon. Relative column/row endpoints move; absolute endpoints retain their anchors. Lowercase references are accepted and translated columns use uppercase letters.
  - Preserve double-quoted strings with doubled quote escapes, quoted sheet names with escaped apostrophes, external-workbook qualifiers, and named sheet spans. Structured-reference bracket groups are lexical islands, including nested groups and apostrophe-escaped special characters: copying `SUM(Table1[Q1])+A1` down/right one cell produces `SUM(Table1[Q1])+B2`. Structured names are not interpreted as A1 coordinates or adjusted using inferred table geometry.
  - Exclude references embedded in identifiers and matches resembling function calls, including whitespace before the opening parenthesis. Existing spill/intersection operators are retained without evaluation. A shifted valid coordinate outside Excel's 16,384-column/1,048,576-row bounds becomes `#REF!`; it is not clamped or emitted as row 0. Out-of-grid source spellings that can be defined names remain unchanged.
  - Translation operates on saved formula text; it does not evaluate a formula, resolve names to cells, or implement the full Excel calculation grammar. The master and cached results remain independent of expansion.
  - The source formula and cached value on a selected master are retained. A dependent receives no inferred formula when expansion fails.
- **Diagnostics**
  - `SHARED_FORMULA_UNRESOLVED` when a selected dependent has no master or the sole valid master has empty formula text.
  - `SHARED_FORMULA_INVALID` takes precedence for a conflicting or invalid declaration. One warning is emitted per affected worksheet group and reason; its locator is `worksheet-part!selected-dependent-reference`.
