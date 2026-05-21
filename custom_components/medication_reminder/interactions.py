"""Drug interaction checking via OpenFDA for Medication Reminder."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import INTERACTION_CACHE_TTL, OPENFDA_LABEL_URL

_LOGGER = logging.getLogger(__name__)


class InteractionChecker:
    """Check for drug interactions using the OpenFDA drug label API."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_timestamp: float = 0.0

    def _is_cache_valid(self) -> bool:
        """Return True if the cache has not expired."""
        return (
            self._cache_timestamp > 0
            and (time.monotonic() - self._cache_timestamp) < INTERACTION_CACHE_TTL
        )

    def invalidate_cache(self) -> None:
        """Force cache invalidation."""
        self._cache.clear()
        self._cache_timestamp = 0.0

    async def _fetch_interaction_text(self, rxcui: str) -> str | None:
        """Fetch the drug_interactions text for a single rxcui from OpenFDA."""
        session = async_get_clientsession(self._hass)
        params = {"search": f'openfda.rxcui:"{rxcui}"', "limit": "1"}
        try:
            async with session.get(
                OPENFDA_LABEL_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                results = data.get("results")
                if not results:
                    return None
                interactions = results[0].get("drug_interactions")
                if isinstance(interactions, list) and interactions:
                    return interactions[0]
                return None
        except aiohttp.ClientError:
            _LOGGER.warning(
                "Failed to fetch interaction data for rxcui %s", rxcui, exc_info=True
            )
            return None

    async def check_interactions(
        self, medications: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Check all configured medications for pairwise interactions.

        Each medication dict should have at least 'name' and optionally 'rxcui'.
        Returns a list of interaction warning dicts.
        """
        if self._is_cache_valid() and self._cache:
            return self._build_warnings(medications, self._cache)

        # Collect medications that have an rxcui
        to_fetch: list[tuple[str, str]] = []
        for med in medications:
            rxcui = str(med.get("rxcui", "")).strip()
            if rxcui:
                to_fetch.append((rxcui, med.get("name", "Unknown")))

        # Fetch all interaction texts concurrently
        results = await asyncio.gather(
            *(self._fetch_interaction_text(rxcui) for rxcui, _ in to_fetch),
            return_exceptions=True,
        )
        interaction_texts: dict[str, dict[str, Any]] = {}
        for (rxcui, name), result in zip(to_fetch, results):
            text = result if isinstance(result, str) else (result or "")
            if isinstance(result, BaseException):
                _LOGGER.warning("Interaction fetch failed for %s: %s", rxcui, result)
                text = ""
            interaction_texts[rxcui] = {"name": name, "text": text or ""}

        self._cache = interaction_texts
        self._cache_timestamp = time.monotonic()

        return self._build_warnings(medications, interaction_texts)

    @staticmethod
    def _build_warnings(
        medications: list[dict[str, Any]],
        interaction_texts: dict[str, dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Parse interaction texts and find mentions of other configured meds."""
        med_names = {
            med.get("name", "").lower(): med.get("name", "")
            for med in medications
            if med.get("name")
        }
        warnings: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for rxcui, info in interaction_texts.items():
            drug_a = info["name"]
            text_lower = info["text"].lower()
            if not text_lower:
                continue
            for name_lower, name_original in med_names.items():
                if name_lower == drug_a.lower():
                    continue
                if name_lower in text_lower:
                    pair = tuple(sorted((drug_a, name_original)))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    # Extract a short snippet around the mention
                    snippet = _extract_snippet(info["text"], name_original, max_len=200)
                    warnings.append(
                        {
                            "drug_a": drug_a,
                            "drug_b": name_original,
                            "warning": snippet,
                            "source": "OpenFDA",
                        }
                    )
        return warnings


def _extract_snippet(text: str, keyword: str, max_len: int = 200) -> str:
    """Extract a short snippet of text around the first mention of keyword."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return text[:max_len] if len(text) > max_len else text
    start = max(0, idx - max_len // 2)
    end = min(len(text), idx + len(keyword) + max_len // 2)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet
