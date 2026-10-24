"""Shared locator helpers for warning/error location strings."""


def part_block_locator(part: str | None, block_id: str | None) -> str:
    """Build a ``part:block_id`` locator string.

    Used consistently by format parsers to identify the source of
    warnings and parse events.
    """
    return ":".join(piece for piece in (part, block_id) if piece)
