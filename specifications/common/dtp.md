# DTP serialization

[COMMON](README.md) / DTP serialization

DTP 1.0 consists of a header followed by format-specific readable content. 

## Fields

### `header`

- **Output**
  - `density=plain format=xlsx` followed by LF.

- **IR**
  - Envelope fields.

- **Parsing**
  - Sort keys lexicographically. DOCX additionally supplies `pagination=last-rendered-hints` and `revision_view=final|original|review`.

### `page marker`

- **Output**
  - A complete line `<page=N>`, positive decimal N.

- **OOXML**
  - DOCX pagination result.

- **IR**
  - Internal page sentinel.

- **Parsing**
  - Restore only parser-created sentinels after escaping source text. Literal source line `<page=2>` becomes `\<page=2>`; a source line with one leading backslash becomes two.

- **Absence and defaults**
  - Only DOCX emits actual pagination milestones.

- **Diagnostics**
  - The escape helper only special-cases zero or one leading backslash; it is not a general reversible encoding of arbitrary backslash runs.

### `content`

- **Output**
  - Readable paragraphs, table text, and object summaries.

- **OOXML**
  - Format-specific IR.

- **Parsing**
  - No general Markdown conversion. Tabs/newlines and summary conventions are defined per format; ordinary source text is not a universal markup language.


## Source references

- [render_plain](../../packages/ooxml_llm_core/src/ooxml_llm_core/doctokens_plain.py#L20)
- [_escape_user_page_markers](../../packages/ooxml_llm_core/src/ooxml_llm_core/doctokens_plain.py#L70)
