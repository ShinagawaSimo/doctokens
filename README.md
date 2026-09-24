# doctokens

Python parsers for DOCX, PPTX, and XLSX, with structured text output, parse diagnostics, and access to embedded resources. Each parser reads OOXML directly. OCR is available through an optional adapter.

[Parser reference](specifications/README.md) · [DOCX](specifications/docx/README.md) · [PPTX](specifications/pptx/README.md) · [XLSX](specifications/xlsx/README.md)

## Install from this repository

Python 3.10 or later:

```sh
python -m pip install -e ./packages/ooxml_llm_core -e ./packages/docx_llm_parser -e ./packages/pptx_llm_parser -e ./packages/xlsx_llm_parser
```

## Parse a document

```python
from docx_llm_parser import parse_docx
from pptx_llm_parser import parse_pptx
from xlsx_llm_parser import parse_xlsx

document = parse_docx("report.docx", density="semantic")
presentation = parse_pptx("slides.pptx", density="structural")
workbook = parse_xlsx("sales.xlsx", density="structural")

print(document.text)
print(document.report.to_dict())
print(document.resources)
```

Use `plain` for readable DTP text, `structural` for DTX structure, or `semantic` for additional parsed semantics. [Density](specifications/common/density.md) defines the format-specific behavior. Inputs can be paths or complete file bytes.

## Read several selections

```python
from docx_llm_parser import open_docx
from xlsx_llm_parser import open_xlsx

with open_docx("report.docx") as session:
    overview = session.render(density="plain")
    first_page = session.render(density="semantic", page_hint=1, span=1)

with open_xlsx("sales.xlsx") as session:
    selected = session.render(sheet="Sales", range_spec="A1:D20")
```

Selection and resource operations are described in the [DOCX interface](specifications/docx/api.md), [PPTX interface](specifications/pptx/api.md), [XLSX interface](specifications/xlsx/api.md), and [session reference](specifications/common/session.md).

## Output examples

DOCX, `semantic`:

```xml
<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final" schema="doctokens-xml" version="1.0"><body><page number="1" /><p>Hello <b>world</b>.</p></body></document>
```

The same document, `plain`:

```text
density=plain format=docx pagination=last-rendered-hints revision_view=final syntax=doctokens-plain/1.0
<page=1>

Hello world.
```

PPTX, `structural`:

```xml
<presentation density="structural" format="pptx" schema="doctokens-xml" version="1.0"><slide number="1"><title placeholder="title">Quarterly report</title></slide></presentation>
```

XLSX, `structural`:

```xml
<workbook density="structural" format="xlsx" schema="doctokens-xml" version="1.0"><sheet name="Sales"><grid ref="A1:B1"><tr number="1"><cell>Total</cell><cell>42</cell></tr></grid></sheet></workbook>
```
