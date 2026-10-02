# doctokens reference

The reference defines how OOXML packages become Doctokens Plain Text (DTP), Doctokens XML (DTX), parse reports, and requested resources.

| Reference | Scope |
| --- | --- |
| [Common](common/README.md) | Package access, serialization, public types, and shared object parsers |
| [DOCX](docx/README.md) | Document flow, text, numbering, tables, annotations, and drawing objects |
| [PPTX](pptx/README.md) | Slides, shapes, inheritance, text, tables, annotations, and media |
| [XLSX](xlsx/README.md) | Worksheets, cells, formulas, formatting, annotations, objects, and queries |
| [Agent tools](agent-tools/README.md) | Direct tool calls, MCP, snapshots, bounded reads, and result retrieval |

## Notation

- XML paths use the prefixes in [Namespaces](common/namespaces.md). A prefix identifies a namespace URI, not a required spelling in the input.
- `element/@attribute` denotes an attribute; `element/text()` denotes character data after XML entity decoding.
- **Output** identifies a DTP fragment, DTX node, public result member, or resource result. XML examples are fragments unless a document root is shown.
- **OOXML** identifies source elements and attributes. **Source** identifies call arguments or derived input where there is no corresponding OOXML field.
- **IR** identifies an intermediate member or operation. Internal types are not a stable Python import API.
- **Absent** means the member or attribute does not exist. `None`, `""`, `0`, and `False` are distinct values.
- Processing steps execute in the stated order. Source order is XML declaration order within the named part.
- Source links identify the code defining a rule. Python excerpts and conversion expressions use implementation identifiers; pseudocode is labeled explicitly.

The public densities are `plain`, `structural`, and `semantic`. Their extraction and visibility rules are defined under [Density](common/density.md). Implementation limits and diagnostic behavior appear beside the affected fields.
