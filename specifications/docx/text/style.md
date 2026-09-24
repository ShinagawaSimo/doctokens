# Styles

[DOCX](../README.md) / Styles

Styles supply explicitly declared reading properties.

## Processing

Missing styles.xml: `MISSING_STYLES`, empty map. Heading, numbering, and format cycles return None/empty and report `STYLE_INHERITANCE_CYCLE`, `STYLE_NUMBERING_INHERITANCE_CYCLE`, or `STYLE_FORMAT_INHERITANCE_CYCLE`. Alignment/border cycles stop without a dedicated warning. Alignment, borders, and run formatting are extracted only with CHARACTER_FORMATTING.

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
  - Use source value or `unknown`.

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
  - Parent style key; follow independently for headings, numbering, alignment, borders, and run format.

### `link`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/w:link/@w:val`

- **IR**
  - `StyleRecord.link: str | None`

- **Parsing**
  - For paragraph run formatting, merge the referenced linked style after basedOn and before this style. Resolve its inheritance with a separate visited set.

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
  - Accept integers 0..9. Invalid values: `INVALID_OUTLINE_LEVEL`; leave None.

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
  - Merge inherited, linked, and direct format. See [emphasis](emphasis.md).

### `is_custom`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/@w:customStyle`

- **IR**
  - `StyleRecord.is_custom: bool`

- **Parsing**
  - `value.lower() in {"1", "true"}`; default false.

### `is_default`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/@w:default`

- **IR**
  - `StyleRecord.is_default: bool`

- **Parsing**
  - `value.lower() in {"1", "true"}`; default false. This flag alone does not apply a style to paragraphs lacking pStyle.

### `resolved_heading_level`

- **Output**
  - Internal style record; visible properties project through their paragraph/run fields.

- **OOXML**
  - `word/styles.xml/w:styles/w:style/outline_level and based_on`

- **IR**
  - `StyleRecord.resolved_heading_level: int | None`

- **Parsing**
  - First resolved outline < 9 yields outline+1. An explicit 9 still follows basedOn in the current resolver.


## Source references

- [StylesParser.parse](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/styles.py#L210)
- [StyleMap](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/styles.py#L20)
