# Package

[COMMON](README.md) / Package

Input is a ZIP/OPC package. No Office application is invoked.

## Fields

### `source`

- **Output**
  - `parse_docx`, `parse_pptx`, `parse_xlsx`, `open_docx`, `open_pptx`, `open_xlsx`.

- **OOXML**
  - ZIP bytes or a filesystem path.

- **IR**
  - `Source = str | Path | bytes`

- **Parsing**
  - Open the package; validate the required main part and archive limits. Main parts: `word/document.xml`, `ppt/presentation.xml`, `xl/workbook.xml`.

- **Diagnostics**
  - Invalid archive, missing required part, or exceeded limit: exception; no success result.

### `max_zip_entries`

- **Output**
  - Input option; no text projection.

- **OOXML**
  - ZIP entry index.

- **IR**
  - `PackageOptions.max_zip_entries: int = 10_000`

- **Parsing**
  - Reject booleans, non-integers, and values <= 0. Enforce against archive entry count.

- **Diagnostics**
  - Invalid option: `ValueError`.

### `max_entry_uncompressed_bytes`

- **Output**
  - Input option; bytes.

- **OOXML**
  - Uncompressed ZIP entry size.

- **IR**
  - `int = 50 * 1024 * 1024`

- **Parsing**
  - Positive integer, excluding bool. Enforce per entry.

### `max_total_uncompressed_bytes`

- **Output**
  - Input option; bytes.

- **OOXML**
  - Sum of uncompressed ZIP entry sizes.

- **IR**
  - `int = 500 * 1024 * 1024`

- **Parsing**
  - Positive integer, excluding bool. Enforce over the archive.


## Source references

- [PackageOptions](../../packages/ooxml_llm_core/src/ooxml_llm_core/options.py#L10)
- [PackageReader](../../packages/ooxml_llm_core/src/ooxml_llm_core/package.py#L31)
