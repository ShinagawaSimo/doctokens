# Reading

[Agent tools](README.md) / Reading

## Fields

### `path` and `document_id`

- **Source**
  - Exactly one must be supplied for a document operation. Unknown fields and implicit type coercions are rejected.
- **Processing**
  - Read directly by path when the target interval is known; inspection is optional.
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
- **Task selection**
  - Use plain when text alone answers the question, structural when source
    coordinates/resource lookup/explicit relationships are needed, and semantic
    when emphasis, color or review context affects interpretation. Tool schemas
    describe this choice; changing density is not a request for exhaustive fields.

### `page_start` and `page_end`

- **Source**
  - Positive, one-based inclusive saved-page hint interval; `page_end >= page_start`.
- **Processing**
  - Omitted end selects `page_start + 2`, bounded by available saved pages. Default start is 1.
  - Each selected page calls `render(page_hint=page, span=1)` and yields a separate complete result in `parts`. Empty pages are marked in selection metadata; intervals continue across empty pages.
  - Navigation uses existing virtual page segments and `pageEnd`, including trailing empty pages. The report's maximum starting block page is not used as the total.
  - These pages are saved-render hints, not a new Word pagination calculation. Existing parser window rules for supplemental content remain applicable.
- **Output**
  - `page_count` and an actionable `next_page` accompany body parts. Each part's
    selection identifies its page; an empty selection is marked. Omit duplicated
    requested/effective intervals and a null continuation at the tail. A start
    beyond the tail returns an empty selected result with the actual page count.

### `slide_start` and `slide_end`

- **Source**
  - Positive, one-based inclusive slide interval; end defaults to start + 2, start defaults to 1.
- **Processing**
  - Use the existing public `slide`/`span` selection. Hidden slides retain their existing semantics.
- **Output**
  - `slide_count` and, when more slides remain, `next_slide` accompany one selected
    presentation result. Text may require character continuation.

### `sheet` and `range_spec`

- **Processing**
  - Without `sheet`, `read_xlsx` selects the first worksheet in saved workbook order and includes the sheet directory. Chartsheets are listed but skipped when choosing this default. A workbook without worksheets returns an empty `parts` list. Explicit sheet names are exact and case-sensitive; reads never automatically cross into another sheet.
  - Without `range_spec`, read a default preview: count emitted cells until reaching 500, finish that entire row, then stop. The final row may exceed 500 cells; a single row wider than 500 is returned in full. This applies to plain, structural and semantic. See [XLSX windows](../xlsx/reading-window.md) for density-specific counting and continuation.
  - A range requires a sheet. Accept an inclusive rectangle (`A1:H20`), inclusive whole rows (`10:20`), or one cell (`A1`, also `A1:A1`). Whole rows cover all source columns without manufacturing missing cells. Explicit ranges are exact and bypass the default preview threshold; oversized text uses the existing result transport and storage limits.
  - Default `inspect_document` always returns the same lightweight XLSX index,
    including after a full session has been opened. It uses `inspect_xlsx`: workbook
    XML and its relationships for sheet names/kinds/visibility and defined names,
    including hidden filter-range names useful for locating declared regions,
    and any external-link declarations needed to assess saved dependencies.
    It does not load shared strings, styles or worksheets and does not claim
    cell/resource counts. `full_parse=true` explicitly opens/reuses a full XLSX
    session and returns its complete report.
  - Use a full session when already available; otherwise preserve the public one-shot sheet/range parse plan. Repeated identical selections use the byte-bounded result cache. Different ranges do not implicitly upgrade to a full workbook session.
- **Output**
  - The sheet directory accompanies the default preview; explicit sheet reads
    do not repeat it. Each part's `selection` identifies the sheet; its `windows`
    retain `returned_range`, emitted `cell_count`, and nonempty crossing merged
    regions. Include `truncated=true` and `next_row` only when applicable. Omit
    repeated input ranges, sheet names, thresholds and null/false defaults.
  - `next_row=73` means the preview ended before source row 73. Continue explicitly
    with the same `document_id`, sheet and density, such as `range_spec="73:144"`.
    There is no opaque data cursor or implicit cross-call position.
  - `read_result.next_offset` retrieves characters of the already selected result,
    not additional rows. Selection metadata is returned once, not on every chunk.

### `full_parse`

- **Default**
  - `false` for `inspect_document` in every format; this is unrelated to the future
    `full` density.
- **Output**
  - Default DOCX/PPTX inspection returns format and navigation without a parse
    report. PPTX includes only hidden/sectioned slide exceptions instead of a
    record for every ordinary visible slide. DOCX retains content-page hints.
  - `true` returns the full parser report, source path and revision. Oversized
    report metadata uses bounded JSON continuation, including a first fragment.

### `whole_document`

- **Default**
  - `false` for DOCX/PPTX. This parameter does not exist for XLSX.
- **Processing**
  - `true` explicitly requests the DOCX/PPTX full body, ignoring their default window. XLSX rejects this argument as unknown; select one sheet and an explicit range instead.

### `options`

- **Processing**
  - DOCX accepts `revision_mode`, `preserve_empty_paragraphs`, `include_runs`, and `include_raw_hints`. XLSX accepts `locale`. Irrelevant format options are rejected.
  - DOCX/PPTX `enable_ocr=true` requires a host-configured OCR provider. OCR is disabled by default. Provider objects, credentials, parser limits, workers, and timeouts are host-owned.
  - Format-specific tools publish only their applicable option fields. Generic
    tools publish the applicability table in the option description.
  - Input schemas express the path/id alternatives and pinned-option constraint;
    a supplied `options={}` is permitted with `document_id`, populated options are rejected.

### Resource and query selection

- **Processing**
  - Resource IDs belong to a particular snapshot. Use its `document_id` when
    following resource descriptors; XLSX's lightweight resource catalog preserves
    the IDs and source order of that snapshot's full parse. IDs from partial
    body plans or newer file versions must not be mixed.
  - Descriptors include `binary_readable`, `renderable`, and `queryable`; presence alone does not promise every operation.
  - `find_xlsx_cells` defaults to 50 matches; [find_document_text](search.md)
    defaults to 20 bounded excerpts. Query defaults to 100 rows; explicit `null`
    removes that row limit. Query operators retain the experimental API rules.
    Results are saved values; formulas are not evaluated.
  - Aggregation runs only when both `group_by` and `aggregates` are nonempty, retaining the parser API's rule.
  - Queries require either a nonempty `table_id` or all of `sheet`, `range_spec`
    and `header_row`. The JSON Schema and tool description expose these alternatives;
    no implicit header row is chosen.

### Runtime information

- **Output**
  - `get_runtime_info` accepts no arguments. It returns active allowed roots,
    result budgets, OCR availability and cache usage without opening a document.
- **Processing**
  - Configuration is fixed for that runtime; host changes require a restart.
