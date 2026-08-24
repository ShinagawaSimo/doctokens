# ooxml-llm-core

Shared OOXML (Open Packaging Conventions) infrastructure used by format-specific LLM-oriented parsers.
Provides ZIP package reading, relationship resolution, XML helpers, and parser warning models.

It also provides the shared `PackageOptions` base for OPC limits/diagnostics
and the `ParseReport` contract (`format`, `schemaVersion`, `manifest`,
`warnings`, `metrics`). Format-specific parsers extend the options and keep
their own document IRs.

This package is parser infrastructure, not a downstream agent runtime. It owns bounded OPC/OOXML access and shared deterministic helpers. Source caching, long-lived read sessions, repeated-file-call deduplication, chunking, retrieval, prompts, and model orchestration remain downstream responsibilities.
