# Sections

[PPTX](../README.md) / Sections

Section membership uses source slide IDs.

## Fields

### `name`

- **Output**
  - `slide/@section`.

- **OOXML**
  - Presentation descendant local-name section/@name.

- **IR**
  - `PresentationSection.name: str`

- **Parsing**
  - Skip empty name; require at least one descendant sldId/@id.

### `slideIds`

- **Output**
  - Internal membership.

- **OOXML**
  - section descendants named sldId with @id.

- **IR**
  - `list[str]`

- **Parsing**
  - Keep source order. The first section containing a given source slide ID supplies its name.


## Source references

- [PptxParser._parse_sections](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/runner.py#L325)
