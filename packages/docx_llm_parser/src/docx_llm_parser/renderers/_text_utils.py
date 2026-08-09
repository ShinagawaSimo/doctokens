"""Text processing logic shared by the renderers.

Run merging, signature computation, and format filtering are pure data
transformations that do not depend on specific output tag syntax.
Both renderers share this module."""

from __future__ import annotations

from ..core.models import Run, RunFormat

RunSignature = tuple[
    object,
    tuple[tuple[str, str], ...],
    tuple[tuple[str, bool | str | None], ...],
]


def merge_text_runs(runs: list[Run]) -> list[Run]:
    """Merge adjacent plain-text runs with the same output semantics, reducing fragmentation in the final output."""
    merged: list[Run] = []
    pending: Run | None = None
    pending_key: RunSignature | None = None

    for run in runs:
        # Runs containing inline objects are not merged; they are added to the result directly.
        if "objects" in run:
            if pending is not None:
                merged.append(pending)
                pending = None
                pending_key = None
            merged.append(run)
            continue

        text = run["text"]
        if not text:
            continue
        signature = run_output_signature(run)
        if pending is not None and pending_key == signature:
            pending["text"] += text
            continue
        if pending is not None:
            merged.append(pending)
        pending = {"text": text}
        if "revision" in run:
            pending["revision"] = run["revision"]
        if "link" in run:
            pending["link"] = run["link"]
        if "format" in run:
            pending["format"] = run["format"]
        pending_key = signature

    if pending is not None:
        merged.append(pending)
    return merged


def run_output_signature(run: Run) -> RunSignature:
    """Generate a stable signature of a run's output-relevant fields, used to decide whether adjacent runs can be merged."""
    link: tuple[tuple[str, str], ...] = ()
    if "link" in run:
        link_items: list[tuple[str, str]] = []
        if "href" in run["link"]:
            link_items.append(("href", run["link"]["href"]))
        if "anchor" in run["link"]:
            link_items.append(("anchor", run["link"]["anchor"]))
        link = tuple(sorted(link_items))
    fmt = tuple(sorted((run.get("format") or {}).items()))
    return (run.get("revision"), link, fmt)


def filter_format(run: Run) -> RunFormat:
    """Filter run formats, removing the default hyperlink style (blue + underline) to avoid output noise."""
    fmt = dict(run.get("format") or {})
    if run.get("link"):
        if fmt.get("color") in {"#0563C1", "#0000FF"}:
            fmt.pop("color", None)
        if fmt.get("underline") is True:
            fmt.pop("underline", None)
    return fmt
