# Reading

[Agent tools](README.md) / Reading

## Fields

### `path` and `document_id`

- **Source**
  - Exactly one must be supplied for a document operation. Unknown fields and implicit type coercions are rejected.
- **Processing**
  - Relative paths resolve against the first configured allowed root. Resolved paths must remain inside an allowed root, refer to a regular file, and have a `.docx`, `.pptx`, or `.xlsx` extension.
  - `document_id` selects a pinned snapshot. Options cannot be changed with an ID; supply a path to select different options.

### `density`

- **Output**
  - `plain`: DTP 1.0, `text/plain`.
  - `structural` and `semantic`: DTX 1.0, `application/xml`.
- **Processing**
  - All three body-reading tools pass the selected density to the public parser/session renderer. Cache keys include density.
- **Default**
  - `structural`. Resource explanations retain semantic density; searches and queries retain structural density.

### `page_start` and `page_end`

- **Source**
  - Positive, one-based inclusive saved-page hint interval; `page_end >= page_start`.
- **Processing**
  - Omitted end selects `page_start + 2`, bounded by available saved pages. Default start is 1.
  - Each selected page calls `render(page_hint=page, span=1)` and yields a separate complete result in `parts`. Empty pages are marked in selection metadata; intervals continue across empty pages.
  - Navigation uses existing virtual page segments and `pageEnd`, including trailing empty pages. The report's maximum starting block page is not used as the total.
  - These pages are saved-render hints, not a new Word pagination calculation. Existing parser window rules for supplemental content remain applicable.
- **Output**
  - `page_count`, `requested`, `effective`, `pagination`, and `next_page` accompany the body parts. `requested` preserves the original interval, while `effective` clips its end to available pages. A start beyond the tail returns an empty result and `effective=null`.

### `slide_start` and `slide_end`

- **Source**
  - Positive, one-based inclusive slide interval; end defaults to start + 2, start defaults to 1.
- **Processing**
  - Use the existing public `slide`/`span` selection. Hidden slides retain their existing semantics.
- **Output**
  - `slide_count` and `next_slide` accompany one complete presentation result.

### `sheet` and `range_spec`

- **Processing**
  - Without a selection, `read_xlsx` returns workbook orientation, not all cells.
  - The initial index uses `inspect_xlsx`: workbook XML and its relationships, sheet names/kinds/visibility, date system, defined names, and external-link descriptions. It does not load shared strings, styles, or worksheets, and does not claim cell/resource counts.
  - A sheet alone explicitly reads that whole sheet. A range requires a sheet; endpoints use the existing `A1:B2` syntax, including `A1:A1` for one cell.
  - Use a full session when already available; otherwise preserve the public one-shot sheet/range parse plan. Repeated identical selections use the byte-bounded result cache. Different ranges do not implicitly upgrade to a full workbook session.

### `whole_document`

- **Default**
  - `false`.
- **Processing**
  - `true` explicitly requests the full body. XLSX rejects a simultaneous sheet/range selection. DOCX/PPTX ignore their default window when this flag is true.

### `options`

- **Processing**
  - DOCX accepts `revision_mode`, `preserve_empty_paragraphs`, `include_runs`, and `include_raw_hints`. XLSX accepts `locale`. Irrelevant format options are rejected.
  - DOCX/PPTX `enable_ocr=true` requires a host-configured OCR provider. OCR is disabled by default. Provider objects, credentials, parser limits, workers, and timeouts are host-owned.

### Resource and query selection

- **Processing**
  - Resource IDs belong to a full parse of a particular snapshot. Use its `document_id` when following resource descriptors; IDs from partial plans or newer file versions must not be mixed.
  - Descriptors include `binary_readable`, `renderable`, and `queryable`; presence alone does not promise every operation.
  - Search defaults to 50 matches. Query defaults to 100 rows; explicit `null` removes that row limit. Query operators and processing retain the existing experimental API rules. Results are saved values; formulas are not evaluated.
  - Aggregation runs only when both `group_by` and `aggregates` are nonempty, retaining the parser API's rule.
