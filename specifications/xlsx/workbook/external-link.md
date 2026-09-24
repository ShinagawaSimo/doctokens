# External workbook references

[XLSX](../README.md) / External workbook references

The output catalogs selected references found inside defined-name expressions.

## Fields

### `target`

- **Output**
  - `external-links/external-link/@target`.

- **OOXML**
  - Bracketed substring in DefinedName.ref.

- **IR**
  - `WorkbookMetadata.external_links: list[str]`

- **Parsing**
  - Regex `\[([^\]]+)\]`; keep strings ending case-insensitively in .xlsx/.xlsm/.xlsb/.xls/.xltx/.xltm. Deduplicate in encounter order. This path does not inventory xl/externalLinks parts or refresh external values.


## Source references

- [_external_link_targets](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/runner.py#L307)
- [_external_links_from_defined_names](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/runner.py#L298)
