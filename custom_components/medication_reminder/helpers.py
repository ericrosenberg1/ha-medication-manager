"""Shared utility functions for Medication Reminder."""
from __future__ import annotations

import voluptuous as vol


def slugify(name: str) -> str:
    """Convert a medication name to a slug suitable for entity IDs.

    Replaces non-alphanumeric characters with underscores, lowercases
    the result, and collapses consecutive underscores.
    """
    base = "".join(ch if ch.isalnum() else "_" for ch in name.lower())
    return "_".join([p for p in base.split("_") if p])


def parse_times(value: str | list[str]) -> list[str]:
    """Parse and normalize time strings into a deduplicated list of ``HH:MM`` values.

    *value* may be a comma-separated string (``"08:00, 20:00"``) or
    a list of individual time strings.  Each token is validated and
    normalized to zero-padded 24-hour format.  Duplicates are removed
    while preserving order.

    Raises ``vol.Invalid`` on malformed or out-of-range times.
    """
    if isinstance(value, list):
        items = value
    else:
        items = [v.strip() for v in value.split(",")]
    out: list[str] = []
    for t in items:
        if not t:
            continue
        try:
            hh, mm = t.split(":")
            hhi = int(hh)
            mmi = int(mm)
        except Exception as err:
            raise vol.Invalid(f"Invalid time format: {t}") from err
        if not (0 <= hhi <= 23 and 0 <= mmi <= 59):
            raise vol.Invalid(f"Invalid time value: {t}")
        out.append(f"{hhi:02d}:{mmi:02d}")
    # remove duplicates, keep order
    seen: set[str] = set()
    unique: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


# Alias kept for backward compatibility with config_flow naming convention.
normalize_times = parse_times
