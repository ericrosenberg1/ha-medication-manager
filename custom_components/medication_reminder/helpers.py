"""Shared utility functions for Medication Reminder."""
from __future__ import annotations

import re

import voluptuous as vol


def slugify(name: str) -> str:
    """Convert a medication name to a slug suitable for entity IDs."""
    base = "".join(ch if ch.isalnum() else "_" for ch in name.lower())
    return "_".join([p for p in base.split("_") if p])


def parse_times(value: str | list[str]) -> list[str]:
    """Parse and normalize time strings into a deduplicated list of HH:MM values.

    Raises vol.Invalid on malformed or out-of-range times.
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
    seen: set[str] = set()
    unique: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


# Alias for backward compatibility with config_flow naming.
normalize_times = parse_times

# Entity ID format validation
ENTITY_ID_RE = re.compile(r"^sensor\.medication_[a-z0-9_]+$")


def is_valid_medication_entity_id(entity_id: str) -> bool:
    """Return True if entity_id matches the medication sensor pattern."""
    return bool(ENTITY_ID_RE.fullmatch(entity_id))


# Healthcare disclaimer text (used in config flow and cards)
DISCLAIMER_TEXT = (
    "This integration is a reminder tool only. It is NOT a medical device and should "
    "NOT be used as a substitute for professional medical advice, diagnosis, or treatment. "
    "Drug interaction data is sourced from OpenFDA and may be incomplete or outdated. "
    "Always consult your physician or pharmacist for medical guidance."
)

DISCLAIMER_SHORT = (
    "Reminder tool only. Not medical advice. Consult your physician."
)
