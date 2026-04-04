"""FDA/NIH API helpers for medication lookup."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

RXTERMS_URL = "https://clinicaltables.nlm.nih.gov/api/rxterms/v3/search"
OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def search_medications(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search RxTerms for medications matching *query*.

    Returns a list of dicts with keys: name, strengths_and_forms, rxcui.
    Returns an empty list on any error.
    """
    query = (query or "").strip()
    if not query:
        return []

    params = {
        "terms": query,
        "ef": "STRENGTHS_AND_FORMS,RXCUIS",
        "maxList": str(max_results),
    }

    try:
        async with session.get(
            RXTERMS_URL, params=params, timeout=REQUEST_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        _LOGGER.warning("RxTerms search failed for %r: %s", query, err)
        return []

    # Response format: [totalCount, codeArray, {extraFields}, displayNames]
    try:
        _count, _codes, extra_fields, display_names = data
    except (ValueError, TypeError):
        _LOGGER.warning("Unexpected RxTerms response format: %s", data)
        return []

    strengths_list = extra_fields.get("STRENGTHS_AND_FORMS", [])
    rxcuis_list = extra_fields.get("RXCUIS", [])

    results: list[dict[str, Any]] = []
    for idx, name in enumerate(display_names):
        strengths = strengths_list[idx] if idx < len(strengths_list) else []
        rxcuis = rxcuis_list[idx] if idx < len(rxcuis_list) else []
        results.append(
            {
                "name": name,
                "strengths_and_forms": strengths if isinstance(strengths, list) else [],
                "rxcui": rxcuis[0] if rxcuis else "",
            }
        )

    return results


async def get_drug_details(
    session: aiohttp.ClientSession,
    rxcui: str,
) -> dict[str, str] | None:
    """Fetch drug label details from OpenFDA for a given RxCUI.

    Returns a dict with dosage_and_administration, drug_interactions,
    warnings, and indications_and_usage (all strings).
    Returns None on any error or if no results are found.
    """
    if not rxcui:
        return None

    params = {
        "search": f'openfda.rxcui:"{rxcui}"',
        "limit": "1",
    }

    try:
        async with session.get(
            OPENFDA_LABEL_URL, params=params, timeout=REQUEST_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        _LOGGER.warning("OpenFDA lookup failed for rxcui=%s: %s", rxcui, err)
        return None

    try:
        result = data["results"][0]
    except (KeyError, IndexError, TypeError):
        _LOGGER.debug("No OpenFDA results for rxcui=%s", rxcui)
        return None

    def _first_str(field: str) -> str:
        val = result.get(field)
        if isinstance(val, list) and val:
            return str(val[0])
        if isinstance(val, str):
            return val
        return ""

    return {
        "dosage_and_administration": _first_str("dosage_and_administration"),
        "drug_interactions": _first_str("drug_interactions"),
        "warnings": _first_str("warnings"),
        "indications_and_usage": _first_str("indications_and_usage"),
    }
