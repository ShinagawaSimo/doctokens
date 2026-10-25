# doctokens-core

Shared Office reading infrastructure used by the Word, Excel and PowerPoint packages.
Provides OPC ZIP package reading, relationships, XML, read-only CFB streams,
output serialization, execution control and parser diagnostics.

It also provides the shared `PackageOptions` base for OPC limits and in-memory diagnostics
and the `ParseReport` contract (`format`, `schemaVersion`, `manifest`,
`warnings`, `metrics`). Format-specific parsers extend the options and keep
their own document IRs.

CFB access is available through `doctokens_core.cfb.CfbReader`. Its entered
lifetime owns the file and its logical streams. Format-specific BIFF or Word/PPT
content interpretation belongs to the application-family packages.

This package owns bounded container access and shared deterministic helpers.
Long-lived orchestration, cross-request caching, retrieval, prompts and model
calls remain downstream responsibilities.
