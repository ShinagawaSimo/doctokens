"""Shared locator helpers for warning/error location strings."""


def part_block_locator(part: str, block_id: str) -> str:
    """Build a ``part:block_id`` locator string.

    Used consistently by format parsers to identify the source of
    warnings and parse events.
    """
    return ":".join(filter(None, [part, block_id]))
