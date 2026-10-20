# Alternate content

[DOCX](../README.md) / Alternate content

`mc:AlternateContent` stores alternative representations of one piece of content.
The DOCX body and ancillary readers select one representation before ordinary
paragraph, run, table or drawing parsing. The namespace of `mc` is
`http://schemas.openxmlformats.org/markup-compatibility/2006`.

## Branch selection

- Resolve each whitespace-separated prefix in `mc:Choice/@Requires` using the
  namespace declarations in scope on that Choice, including local overrides.
  Prefix spelling alone never establishes support. Every required namespace must
  be supported; an empty Requires or an unbound prefix makes that Choice ineligible.
- Consider Choices in source order. Select the first whose requirements and
  content are processable by the receiving content parser. Preflight has no effects
  on fields, bookmarks, comment anchors, revisions or page counters.
- Supported reading namespaces are WordprocessingML, Wordprocessing DrawingML,
  DrawingML main/picture/chart/diagram, OMML, VML and Word 2010 wordprocessingShape.
  Recognition of these namespaces does not promise full graphical rendering.
  An unknown content node or a drawing/OLE that would only become an opaque
  placeholder does not qualify a Choice. DrawingML text boxes, bound images,
  chart references and SmartArt references use their existing reading capabilities;
  VML Choices qualify for text-box content or image references bound to the
  owning part's resource index.
- A valid empty branch succeeds. Lack of visible text alone does not trigger
  fallback: empty text boxes, field boundaries and content omitted by the selected
  revision view are not evidence of failure.
- If no Choice qualifies, select `mc:Fallback`, when present, and process its
  children using the ordinary unsupported-content diagnostics. If neither a
  processable Choice nor a Fallback exists, emit `ALTERNATE_CONTENT_UNRESOLVED`
  and omit that alternate's content.
- Replace the compatibility wrapper with the selected children in source order.
  Never concatenate Choice and Fallback or deduplicate by text. Identical text
  from separate source objects remains separate content.
- Resolve nested alternates before committing the enclosing Choice. Records and
  parser effects from a rejected branch are discarded. A nested unresolved
  alternate makes its enclosing Choice unprocessable.

Selection precedes density projection and does not depend on `include_raw_hints`.
All densities use the same capability checks for parts included by their parse
plan. XML syntax failures and package limits remain ordinary parser failures;
fallback does not suppress a broken XML part or an unexpected programming error.

## `report.manifest.alternateContent`

- **Output**
  - An ordered array of selection records, omitted when no alternates were read.
  - Successful Choice/Fallback selection creates no warning and adds no markup to
    the reading body.
- **Fields**
  - `part`: the source XML part path.
  - `index`: one-based source-order AlternateContent index within that part.
    Indices count nested alternates in unselected branches, so gaps are possible.
  - `branch`: `Choice`, `Fallback`, or `none`.
  - `choiceIndex`: one-based Choice index, present only for selected Choices.
  - `requires`: selected Choice prefix-to-namespace-URI map; `{}` for Fallback/none.
  - `reason`: `supported_choice`, `no_supported_choice`, `choice_unprocessable`,
    or `missing_fallback`.
  - `rejectedChoices`: earlier rejected Choices with `choiceIndex`, `requires`,
    and `reason` (`unsupported_namespace`, `invalid_requires`, or
    `unprocessable_content`). An unbound prefix has a null URI.
- **Scope**
  - Records describe XML parts actually read by the parse plan, before page-window
    or density projection. Ancillary records follow those for the main body.
  - Resource indexing still follows package relationships; selection does not
    remove unused image resources from the package-wide directory.
  - For unresolved alternates, the diagnostic locator is
    `part:AlternateContent[index]`.

## Example

Given a run containing a Choice with `Requires="shape"`, where `shape` is bound
to `http://schemas.microsoft.com/office/word/2010/wordprocessingShape`, and both
that Choice and its VML Fallback contain the same caption, the output contains
one text box. The report records `branch="Choice"`, `choiceIndex=1` and the
resolved URI, even though the producer used `shape` instead of the usual `wps`.
