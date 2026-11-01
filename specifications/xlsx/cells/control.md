# Cell controls

[XLSX](../README.md) / Cell controls

The supported saved control is a checkbox. XML reading output represents its
current value once through checked; plain uses a compact checkbox marker.
Underlying saved cell values remain available to search/query operations.

## Fields

### `kind`

- **Output**
  - Both XML densities: cell/@control="checkbox". Plain uses [Checkbox true],
    [Checkbox false], or [Checkbox] followed by a distinct unknown saved value.
- **OOXML**
  - Feature-property bag type Checkbox, resolved through style xfComplement,
    XFComplements, XFComplement, XFControls and CellControl relationships.
- **IR**
  - CellControl.kind: str.
- **Parsing**
  - Preserve a declared control even when its value is empty/unknown. Editing
    defaults are not extracted into the control reading model. Comments and
    explicit links keep their independent reading contracts.
- **Diagnostics**
  - Malformed optional bag XML yields XLSX_CATALOG_XML_INVALID; unresolved
    declared bag references retain existing catalog diagnostics. Saved cell
    values are not replaced by a guessed control state.

### `checked`

- **Output**
  - Both XML densities: checked=true or checked=false. Do not repeat TRUE/FALSE
    as cell character data. Unknown values omit checked and retain their text.
- **OOXML**
  - Current saved display text TRUE/FALSE of the declared checkbox cell.
- **IR**
  - CellControl.checked: bool, absent when unknown. Cell.text remains the saved
    value; no duplicate control value/state/default is stored.
- **Parsing**
  - TRUE maps to true and FALSE to false. Empty/error/other values are not false.
    The parser does not toggle, evaluate or default a checkbox.
