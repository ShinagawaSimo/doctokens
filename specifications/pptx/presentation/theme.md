# Theme colors

[PPTX](../README.md) / Theme colors

Theme slots provide base colors for DrawingML scheme-color resolution.

## Fields

### `part`

- **Output**
  - Theme source; no DTX attribute.

- **OOXML**
  - Relationship type `http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme`.

- **IR**
  - `ThemeParser` selected part.

- **Parsing**
  - Prefer a relationship from `ppt/presentation.xml`, then the first from `ppt/slideMasters/` in relationship order. A master-specific request uses its first non-null target, falling back to deck selection.

- **Absence and defaults**
  - No resolved theme: Office defaults.

- **Diagnostics**
  - `THEME_PART_MISSING`: missing relationship or target; `THEME_XML_INVALID`: malformed XML; `THEME_MISSING_CLRSCHEME`: no descendant with local name `clrScheme`. All use default colors.

### `color`

- **Output**
  - Resolved color for a named slot.

- **OOXML**
  - `a:clrScheme/{slot}/a:srgbClr/@val` or `a:sysClr/@lastClr`.

- **IR**
  - `LayoutContext.theme: dict[str, str]`

- **Parsing**
  - For each slot below, start with its default. Read children selected by local name; the first supported color child with a six-character value yields `"#" + value.upper()`. Later valid duplicate slot elements replace earlier ones. No hexadecimal validation occurs in this step.

- **Absence and defaults**
  - Missing or unrecognized slot color: retain its default.


## Source references

- [ThemeParser](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/theme.py#L49)
- [ThemeParser._slot_value](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/theme.py#L143)

## Slots

| Slot | Default |
| --- | --- |
| `dk1` | `#000000` |
| `lt1` | `#FFFFFF` |
| `dk2` | `#44546A` |
| `lt2` | `#E7E6E6` |
| `accent1` | `#4472C4` |
| `accent2` | `#ED7D31` |
| `accent3` | `#A5A5A5` |
| `accent4` | `#FFC000` |
| `accent5` | `#5B9BD5` |
| `accent6` | `#70AD47` |
| `hlink` | `#0563C1` |
| `folHlink` | `#954F72` |
