# Bullets and numbering

[PPTX](../README.md) / Bullets and numbering

List labels remain visible in every density. XML also retains explicit paragraph
levels; a marker's font is interpreted only to recover reading content.

## Fields

### `text`

- **Output**
  - Visible list prefix, one space, then source paragraph text. XML attributes
    describe that existing prefix; they do not request a second rendered label.
- **OOXML**
  - `a:p` list declarations, runs, fields, breaks and equations.
- **IR**
  - `Paragraph.text: str`; `Paragraph.runs: list[Run]`.
- **Parsing**
  - Resolve the effective list kind before adding a prefix. Preserve each
    paragraph's runs for the XML projection. Do not generate a label for a
    paragraph whose runs contain no non-whitespace text or equation.

### `level`

- **Output**
  - XML paragraph `@level`; always present inside multi-paragraph `textbox`.
    On single-paragraph objects, omit zero only when no list kind exists.
  - Plain: two spaces per level, clamped to 0..8 for indentation.
- **OOXML**
  - `a:pPr/@lvl`.
- **IR**
  - `Paragraph.level: int`.
- **Parsing**
  - Parse an integer, default 0 when absent/malformed. Inherited style lookup
    uses the requested level, then level 0. Nesting does not alter object ids.

### `bullet`

- **Output**
  - Visible prefix and XML `@bullet`.
- **OOXML**
  - Direct `a:buChar/@char` or inherited bullet.
- **IR**
  - `Paragraph.bullet: str`.
- **Parsing**
  - Direct `buNone` suppresses the list. Direct `buChar` takes precedence over
    automatic numbering; an empty character defaults to `•`. Direct numbering
    replaces an inherited bullet. Inherited `listNone` suppresses inherited labels.
  - Interpret known symbol-font codes through the mappings below. For a known
    symbol font, an explicitly declared symbol charset, or a private-use code
    without a reliable mapping, emit neutral `•` and retain source evidence.
  - Other ordinary Unicode bullet text remains unchanged.

### `bulletSource`

- **Output**
  - Both XML densities: `@bullet-source` when symbol/private-use interpretation
    was required; plain emits only the resolved or neutral marker.
- **OOXML**
  - The original effective `buChar/@char`.
- **IR**
  - `Paragraph.bulletSource: str`.
- **Parsing**
  - Preserve the original string, including a private-use encoding. A substituted
    marker is not evidence that the original glyph was decoded.

### `bulletFont`

- **Output**
  - Both XML densities: `@bullet-font` with `bullet-source`, when a nonempty
    effective font declaration is available. This is decoding provenance, not
    a general typography projection.
- **OOXML**
  - `a:buFont/@typeface` and `@charset`, or the font selected by `buFontTx`.
- **IR**
  - Paragraph/source font; inherited `ParagraphStyle.bulletFont`,
    `bulletFontSymbol`, `textFont`, `textFontSymbol`.
- **Parsing**
  - A direct `buFont` overrides inherited marker font. `buFontTx` clears that
    fixed font; use paragraph defaults and the first text run's declared font,
    falling back to inherited text defaults. Read `sym` before `latin`.
  - Symbol charset is hexadecimal value 02. Font-name matching is case-insensitive.
  - Recognized symbol families: Wingdings, Wingdings 2, Wingdings 3, Webdings,
    Symbol. Only these exact supported mappings are interpreted:
    - Wingdings: 6C → `●`, 6E → `■`, 75 → `◆`, A7 → `▪`.
    - Symbol: B7 → `•`.
  - F000..F0FF codes use the corresponding low byte. All source characters must
    map reliably; otherwise the whole marker uses neutral `•`. No font loading,
    rasterization or installed-font dependency is required.

### `numberType`

- **Output**
  - Visible formatted counter and XML `@number-type`.
- **OOXML**
  - Direct `a:buAutoNum/@type` or inherited numbering type.
- **IR**
  - `Paragraph.numberType: str`.
- **Parsing**
  - Default `arabicPeriod`; counter key `(number_type, level)` is scoped to one
    text body. Format with the DrawingML number formatter.

### `startAt`

- **Output**
  - XML `@start-at` for automatic numbering.
- **OOXML**
  - Direct `a:buAutoNum/@startAt` or inherited value.
- **IR**
  - `Paragraph.startAt: int`.
- **Parsing**
  - Parse a direct integer, falling back to inherited start and then 1. The first
    use of a counter key uses that value; later uses increment. No deeper-level
    reset rule or implicit restart is introduced.

### `number`

- **Output**
  - XML `@number` for the actual counter used by this paragraph's visible label.
- **IR**
  - `Paragraph.number: int`.
- **Parsing**
  - Assign only when a nonempty automatically numbered paragraph consumes its
    counter. Empty tail paragraphs do not advance numbering.
