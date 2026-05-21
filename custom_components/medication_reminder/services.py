"""Service handlers for the Medication Reminder integration."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
# async_extract_entity_ids handles both entity_id in data and target selectors
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STATE_TAKEN, STATE_SKIPPED, DEFAULT_SNOOZE_MINUTES
from .history import HistoryManager

_LOGGER = logging.getLogger(__name__)


class MedicationServices:
    """Registers and handles all medication_reminder domain services."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    def _entity(self, entity_id: str):
        """Look up a medication entity by ID."""
        return self._hass.data[DOMAIN]["entities"].get(entity_id)

    def _history(self) -> HistoryManager:
        """Return the shared HistoryManager."""
        return self._hass.data[DOMAIN]["history"]

    async def async_mark_taken(self, call: ServiceCall) -> None:
        entity_ids = async_extract_entity_ids(self._hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        for eid in entity_ids:
            entity = self._entity(eid)
            if not entity:
                raise HomeAssistantError(f"Medication entity not found: {eid}")
            await entity.async_mark(STATE_TAKEN)

    async def async_mark_skipped(self, call: ServiceCall) -> None:
        entity_ids = async_extract_entity_ids(self._hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        for eid in entity_ids:
            entity = self._entity(eid)
            if not entity:
                raise HomeAssistantError(f"Medication entity not found: {eid}")
            await entity.async_mark(STATE_SKIPPED)

    async def async_mark_snoozed(self, call: ServiceCall) -> None:
        entity_ids = async_extract_entity_ids(self._hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        raw_minutes = call.data.get("minutes")
        for eid in entity_ids:
            entity = self._entity(eid)
            if not entity:
                raise HomeAssistantError(f"Medication entity not found: {eid}")
            try:
                minutes = int(raw_minutes) if raw_minutes is not None else int(entity.snooze_minutes)
            except (TypeError, ValueError):
                minutes = DEFAULT_SNOOZE_MINUTES
            minutes = max(1, min(1440, minutes))
            await entity.async_snooze(minutes)

    async def async_mark_pending(self, call: ServiceCall) -> None:
        entity_ids = async_extract_entity_ids(self._hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        for eid in entity_ids:
            entity = self._entity(eid)
            if not entity:
                raise HomeAssistantError(f"Medication entity not found: {eid}")
            await entity.async_mark("Pending")

    async def async_refill_set(self, call: ServiceCall) -> None:
        entity_ids = async_extract_entity_ids(self._hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        remaining = call.data.get("remaining")
        threshold = call.data.get("threshold")
        units = call.data.get("units_per_intake")
        if remaining is None and threshold is None and units is None:
            raise HomeAssistantError("Provide at least one of remaining, threshold, units_per_intake")
        hist = self._history()
        for eid in entity_ids:
            cur = hist.get_refill(eid) or {"remaining": 0, "threshold": 0, "units_per_intake": 1, "alerted": False}
            await hist.set_refill(
                eid,
                remaining=int(remaining if remaining is not None else cur["remaining"]),
                threshold=int(threshold if threshold is not None else cur["threshold"]),
                units_per_intake=int(units if units is not None else cur["units_per_intake"]),
                alerted=bool(cur.get("alerted", False)),
            )

    async def async_refill_add(self, call: ServiceCall) -> None:
        entity_ids = async_extract_entity_ids(self._hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        amount = call.data.get("amount")
        if amount is None:
            raise HomeAssistantError("amount is required")
        amount = int(amount)
        hist = self._history()
        for eid in entity_ids:
            cur = hist.get_refill(eid)
            if not cur:
                continue
            new_remaining = max(0, int(cur.get("remaining", 0)) + amount)
            await hist.adjust_refill(eid, remaining=new_remaining, alerted=False)

    async def async_refill_acknowledge(self, call: ServiceCall) -> None:
        entity_ids = async_extract_entity_ids(self._hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        hist = self._history()
        for eid in entity_ids:
            await hist.adjust_refill(eid, alerted=False)
