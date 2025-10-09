"""Medication Reminder integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.config_entries import ConfigEntryState

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
    # Ensure domain data is initialized
    store = hass.data.setdefault(DOMAIN, {})
    store.setdefault("entities", {})
    if "history" not in store:
        history = HistoryManager(hass)
        await history.async_load()
        store["history"] = history

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    _LOGGER.debug("%s: sensor platform forwarded for entry %s", DOMAIN, entry.entry_id)

    # Register domain services once
    if not store.get("services_registered"):
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
        # Optional reset service
        async def mark_pending(call: ServiceCall):
            entity_ids = async_extract_entity_ids(hass, call)
            if not entity_ids:
                raise HomeAssistantError("No entity_id or target provided")
            for eid in entity_ids:
                entity = hass.data[DOMAIN]["entities"].get(eid)
                if not entity:
                    raise HomeAssistantError(f"Medication entity not found: {eid}")
                await entity.async_mark("Pending")
        hass.services.async_register(DOMAIN, "mark_pending", mark_pending)

        # Refill helpers
        async def refill_set(call: ServiceCall):
            entity_ids = async_extract_entity_ids(hass, call)
            if not entity_ids:
                raise HomeAssistantError("No entity_id or target provided")
            remaining = call.data.get("remaining")
            threshold = call.data.get("threshold")
            units = call.data.get("units_per_intake")
            if remaining is None and threshold is None and units is None:
                raise HomeAssistantError("Provide at least one of remaining, threshold, units_per_intake")
            hist: HistoryManager = hass.data[DOMAIN]["history"]
            for eid in entity_ids:
                cur = hist.get_refill(eid) or {"remaining": 0, "threshold": 0, "units_per_intake": 1, "alerted": False}
                await hist.set_refill(
                    eid,
                    remaining=int(remaining if remaining is not None else cur["remaining"]),
                    threshold=int(threshold if threshold is not None else cur["threshold"]),
                    units_per_intake=int(units if units is not None else cur["units_per_intake"]),
                    alerted=bool(cur.get("alerted", False)),
                )

        async def refill_add(call: ServiceCall):
            entity_ids = async_extract_entity_ids(hass, call)
            if not entity_ids:
                raise HomeAssistantError("No entity_id or target provided")
            amount = call.data.get("amount")
            if amount is None:
                raise HomeAssistantError("amount is required")
            try:
                amount = int(amount)
            except (TypeError, ValueError) as err:
                raise HomeAssistantError("amount must be integer") from err
            hist: HistoryManager = hass.data[DOMAIN]["history"]
            for eid in entity_ids:
                cur = hist.get_refill(eid)
                if not cur:
                    continue
                new_remaining = max(0, int(cur.get("remaining", 0)) + amount)
                await hist.adjust_refill(eid, remaining=new_remaining, alerted=False)

        async def refill_acknowledge(call: ServiceCall):
            entity_ids = async_extract_entity_ids(hass, call)
            if not entity_ids:
                raise HomeAssistantError("No entity_id or target provided")
            hist: HistoryManager = hass.data[DOMAIN]["history"]
            for eid in entity_ids:
                await hist.adjust_refill(eid, alerted=False)

        hass.services.async_register(DOMAIN, "refill_set", refill_set)
        hass.services.async_register(DOMAIN, "refill_add", refill_add)
        hass.services.async_register(DOMAIN, "refill_acknowledge", refill_acknowledge)
        store["services_registered"] = True
        _LOGGER.debug("%s: services registered", DOMAIN)

    # Register global mobile actions listener once
    if not store.get("mobile_unsub"):
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
            elif action in ("MED_SKIP", "SKIP", "SKIPPED", "MED_DISMISS", "DISMISS"):
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

        store["mobile_unsub"] = hass.bus.async_listen("mobile_app_notification_action", _handle_mobile_action)
        _LOGGER.debug("%s: listening for mobile_app_notification_action", DOMAIN)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if not ok:
        return False

    # If no more loaded entries, remove services and listeners
    entries = hass.config_entries.async_entries(DOMAIN)
    any_loaded = any(e.state == ConfigEntryState.LOADED and e.entry_id != entry.entry_id for e in entries)
    store = hass.data.get(DOMAIN, {})
    if not any_loaded:
        # Unregister services
        for svc in ("mark_taken", "mark_skipped", "mark_snoozed", "mark_pending", "refill_set", "refill_add", "refill_acknowledge"):
            if hass.services.has_service(DOMAIN, svc):
                hass.services.async_remove(DOMAIN, svc)
        # Remove mobile listener
        unsub = store.get("mobile_unsub")
        if unsub:
            try:
                unsub()
            except Exception:  # best-effort
                pass
            store["mobile_unsub"] = None
        # Clear entities map and history manager
        store.get("entities", {}).clear()
        store.pop("history", None)
        store["services_registered"] = False
    return True
