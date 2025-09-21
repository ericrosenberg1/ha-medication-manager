"""Medication Reminder integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_entity_ids

from .const import (
    DOMAIN,
    STATE_TAKEN,
    STATE_SKIPPED,
    DEFAULT_SNOOZE_MINUTES,
)
from .history import HistoryManager
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medication Reminder from a config entry."""
    # Keep a mapping of entity_id -> entity instance for service handlers
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("entities", {})
    if "history" not in hass.data[DOMAIN]:
        history = HistoryManager(hass)
        await history.async_load()
        hass.data[DOMAIN]["history"] = history

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    _LOGGER.debug("%s: sensor platform forwarded for entry %s", DOMAIN, entry.entry_id)

    # Services operate on medication entities by entity_id
    async def mark_taken(call: ServiceCall):
        entity_ids = async_extract_entity_ids(hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        for eid in entity_ids:
            entity = hass.data[DOMAIN]["entities"].get(eid)
            if not entity:
                raise HomeAssistantError(f"Medication entity not found: {eid}")
            await entity.async_mark(STATE_TAKEN)
            await hass.data[DOMAIN]["history"].record(eid, STATE_TAKEN, dt_util.now().isoformat())

    async def mark_skipped(call: ServiceCall):
        entity_ids = async_extract_entity_ids(hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        for eid in entity_ids:
            entity = hass.data[DOMAIN]["entities"].get(eid)
            if not entity:
                raise HomeAssistantError(f"Medication entity not found: {eid}")
            await entity.async_mark(STATE_SKIPPED)
            await hass.data[DOMAIN]["history"].record(eid, STATE_SKIPPED, dt_util.now().isoformat())

    async def mark_snoozed(call: ServiceCall):
        entity_ids = async_extract_entity_ids(hass, call)
        if not entity_ids:
            raise HomeAssistantError("No entity_id or target provided")
        raw_minutes = call.data.get("minutes")
        for eid in entity_ids:
            entity = hass.data[DOMAIN]["entities"].get(eid)
            if not entity:
                raise HomeAssistantError(f"Medication entity not found: {eid}")
            try:
                minutes = int(raw_minutes) if raw_minutes is not None else int(entity.snooze_minutes)
            except (TypeError, ValueError):
                minutes = DEFAULT_SNOOZE_MINUTES
            if minutes < 1:
                minutes = 1
            if minutes > 1440:
                minutes = 1440
            await entity.async_snooze(minutes)
            await hass.data[DOMAIN]["history"].record(eid, "Snoozed", dt_util.now().isoformat())

    hass.services.async_register(DOMAIN, "mark_taken", mark_taken)
    hass.services.async_register(DOMAIN, "mark_skipped", mark_skipped)
    hass.services.async_register(DOMAIN, "mark_snoozed", mark_snoozed)
    _LOGGER.debug("%s: services registered", DOMAIN)

    # Actionable mobile notifications handler
    async def _handle_mobile_action(event):
        data = event.data or {}
        action = str(data.get("action", "")).upper()
        ad = data.get("action_data", {}) or {}
        entity_id = ad.get("entity_id") or data.get("tag")
        if not entity_id:
            return
        entity = hass.data[DOMAIN]["entities"].get(entity_id)
        if not entity:
            return
        if action in ("MED_TAKEN", "TAKEN"):
            await entity.async_mark(STATE_TAKEN)
            await hass.data[DOMAIN]["history"].record(entity_id, STATE_TAKEN, dt_util.now().isoformat())
        elif action in ("MED_SKIP", "SKIP", "SKIPPED"):
            await entity.async_mark(STATE_SKIPPED)
            await hass.data[DOMAIN]["history"].record(entity_id, STATE_SKIPPED, dt_util.now().isoformat())
        elif action in ("MED_SNOOZE", "SNOOZE", "SNOOZED"):
            minutes = ad.get("minutes")
            try:
                minutes = int(minutes) if minutes is not None else int(entity.snooze_minutes)
            except (TypeError, ValueError):
                minutes = DEFAULT_SNOOZE_MINUTES
            if minutes < 1:
                minutes = 1
            if minutes > 1440:
                minutes = 1440
            await entity.async_snooze(minutes)
            await hass.data[DOMAIN]["history"].record(entity_id, "Snoozed", dt_util.now().isoformat())

    hass.bus.async_listen("mobile_app_notification_action", _handle_mobile_action)
    _LOGGER.debug("%s: listening for mobile_app_notification_action", DOMAIN)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])
