# Styles

[DOCX](../README.md) / Styles

Styles supply explicitly declared reading properties.

## Processing

The [style reader](../../../packages/doctokens_word/src/doctokens_word/docx/ooxml/style_reader.py) reads styles.xml; the [style index](../../../packages/doctokens_word/src/doctokens_word/docx/ooxml/styles.py) resolves inheritance. Missing styles.xml reports `MISSING_STYLES` and supplies empty defaults. Cycles stop at the repeated style, retain the collected declarations, and report `STYLE_INHERITANCE_CYCLE`. BasedOn follows styles of the same type. Alignment, borders, colors, and run formatting are extracted only when character formatting is requested; heading and numbering resolution also operate at lower densities.

## Fields

### `style_id`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/@w:styleId`

- **IR**
  - `StyleRecord.style_id: str`

- **Parsing**
  - Required nonempty key. Skip records without it; a later duplicate replaces the previous record.

### `type`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/@w:type`

- **IR**
  - `StyleRecord.type: str`

- **Parsing**
  - Use the source value; the OOXML default when the attribute is absent is `paragraph`.

### `name`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:name/@w:val`

- **IR**
  - `StyleRecord.name: str | None`

- **Parsing**
  - Copy; the name does not establish a heading.

### `based_on`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:basedOn/@w:val`

- **IR**
  - `StyleRecord.based_on: str | None`

- **Parsing**
  - Parent style key within the same style type. The nearest explicit property wins within a basedOn chain, including explicit false and outline 9. Borders merge by side.

### `link`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:link/@w:val`

- **IR**
  - `StyleRecord.link: str | None`

- **Parsing**
  - Retain the paragraph/character UI pairing. A link does not implicitly apply a second style to the same run. Paragraph and character references select their own typed hierarchy levels.

### `next`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:next/@w:val`

- **IR**
  - `StyleRecord.next: str | None`

- **Parsing**
  - Retain only; does not change subsequent paragraph styles.

### `alignment`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:pPr/w:jc/@w:val`

- **IR**
  - `StyleRecord.alignment: str | None`

- **Parsing**
  - First explicit value through basedOn; see [paragraph alignment](paragraph.md#align).

### `borders`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:pPr/w:pBdr`

- **IR**
  - `StyleRecord.borders: ParagraphBorders`

- **Parsing**
  - Inherited sides, then direct sides; see [borders](border.md).

### `outline_level`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:pPr/w:outlineLvl/@w:val`

- **IR**
  - `StyleRecord.outline_level: int | None`

- **Parsing**
  - Accept integers 0..9. An outline element with missing/invalid value reports `INVALID_OUTLINE_LEVEL`; leave None and allow inheritance. A missing element is simply absent.

### `numbering_num_id`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:pPr/w:numPr/w:numId/@w:val`

- **IR**
  - `StyleRecord.numbering_num_id: str | None`

- **Parsing**
  - First explicit numbering ID through basedOn.

### `numbering_level`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:pPr/w:numPr/w:ilvl/@w:val`

- **IR**
  - `StyleRecord.numbering_level: int | None`

- **Parsing**
  - If numId exists, parse int, default 0; malformed value gives `INVALID_STYLE_NUMBERING_LEVEL`, fallback 0.

### `run_format`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:rPr`

- **IR**
  - `StyleRecord.run_format: RunFormat`

- **Parsing**
  - Resolve inherited properties within each style type, then combine document defaults, table, paragraph, character, and direct formatting as defined below. Preserve explicit clear values until final visible projection. See [emphasis](emphasis.md).

### `is_custom`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/@w:customStyle`

- **IR**
  - `StyleRecord.is_custom: bool`

- **Parsing**
  - `value.lower() in {"1", "true", "on"}`; default false.

### `is_default`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/@w:default`

- **IR**
  - `StyleRecord.is_default: bool`

- **Parsing**
  - `value.lower() in {"1", "true", "on"}`; default false. Select the default style of the requested type when its reference is absent, missing, or points to another style type.

### `document_defaults`

- **Output**
  - Effective reading properties; default/provenance records are not emitted.
- **OOXML**
  - `w:docDefaults/w:pPrDefault/w:pPr` and `w:rPrDefault/w:rPr`.
- **IR**
  - `StyleMap.defaults`, separate from source style records.
- **Parsing**
  - Use document defaults before table/paragraph properties and run-format layers. A default paragraph style supplies heading, numbering, alignment, borders, and run properties even without pStyle. A default character style supplies its run properties even without rStyle. Table defaults apply only inside tables.

### `toggle_cascade`

- **Output**
  - Effective bold, italic, small-caps, and single-strike reading semantics.
- **OOXML**
  - ISO/IEC 29500-1 §17.7.3: toggle properties across style hierarchy levels.
- **IR**
  - Effective `Run.format` after resolution.
- **Parsing**
  - Resolve the nearest explicit value within each basedOn chain; do not XOR ancestors within the same level.
  - A direct run value is absolute. Otherwise, a true document-default value makes the property true; when it is not true, XOR the resolved table, paragraph, and character values. Missing/false layer values contribute false.
  - Example: paragraph bold=true plus character bold=true gives ordinary text; direct bold=true restores bold. Two paragraph ancestors both declaring bold=true still resolve to one paragraph-level true.
  - Underline, double strike, vertical alignment, colors, and highlights use ordinary property precedence, not toggle XOR. Single/double strike share the final `s` wrapper.

### `table_regions`

- **Output**
  - Conditional text properties in cell paragraphs; semantic cell `@background` for resolved cell shading.
- **OOXML**
  - `w:style[@w:type="table"]/w:tblStylePr`; table `tblStyle`, `tblLook`, row/column band sizes, and row/cell/paragraph `cnfStyle`.
- **IR**
  - `StyleRecord.table_regions`; effective per-cell and per-paragraph table context.
- **Parsing**
  - Resolve table basedOn inheritance, then wholeTable, vertical bands, horizontal bands, first/last rows, first/last columns, and corners nw/ne/sw/se, in that precedence order. Resolve each region's inheritance before combining regions.
  - Decode tblLook hexadecimal bits and explicit on/off attributes. By default apply bands and omit edge conditions. Honor band sizes, consecutive header rows, logical grid coordinates and spans, and explicit saved cnfStyle flags. Row tblPrEx exceptions use the selected revision-view property set.
  - Direct paragraph/run properties remain later layers; direct cell shading overrides inherited cell shading. Explicit automatic/nil shading clears inherited fill. Nested tables receive their own table-style context.
- **Diagnostics**
  - Invalid style band sizes report `INVALID_TABLE_BAND_SIZE`; use inherited/default size 1.
- **Limits**
  - This cascade restores the properties supported by the reading model. It does not introduce full theme-font resolution, unsupported typography, table widths/heights, or editable geometry.
