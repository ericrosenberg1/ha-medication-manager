"""Medication Reminder integration for Home Assistant."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    STATE_TAKEN,
    STATE_SKIPPED,
    DEFAULT_SNOOZE_MINUTES,
)
from .helpers import is_valid_medication_entity_id
from .history import HistoryManager
from .sentry import maybe_init_sentry
from .services import MedicationServices

# Initialise Sentry on first import — no-op unless MEDREM_SENTRY_DSN is set
# on the host HA instance AND sentry-sdk is installed. End users get no
# telemetry by default.
maybe_init_sentry()

_LOGGER = logging.getLogger(__name__)

# Service schemas
MARK_SCHEMA = vol.Schema({
    vol.Optional("entity_id"): cv.entity_ids,
})

SNOOZE_SCHEMA = vol.Schema({
    vol.Optional("entity_id"): cv.entity_ids,
    vol.Optional("minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
})

REFILL_SET_SCHEMA = vol.Schema({
    vol.Optional("entity_id"): cv.entity_ids,
    vol.Optional("remaining"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional("threshold"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional("units_per_intake"): vol.All(vol.Coerce(int), vol.Range(min=1)),
})

REFILL_ADD_SCHEMA = vol.Schema({
    vol.Optional("entity_id"): cv.entity_ids,
    vol.Required("amount"): vol.All(vol.Coerce(int)),
})

REFILL_ACK_SCHEMA = vol.Schema({
    vol.Optional("entity_id"): cv.entity_ids,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medication Reminder from a config entry."""
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
        _svc = MedicationServices(hass)
        hass.services.async_register(DOMAIN, "mark_taken", _svc.async_mark_taken, schema=MARK_SCHEMA)
        hass.services.async_register(DOMAIN, "mark_skipped", _svc.async_mark_skipped, schema=MARK_SCHEMA)
        hass.services.async_register(DOMAIN, "mark_snoozed", _svc.async_mark_snoozed, schema=SNOOZE_SCHEMA)
        hass.services.async_register(DOMAIN, "mark_pending", _svc.async_mark_pending, schema=MARK_SCHEMA)
        hass.services.async_register(DOMAIN, "refill_set", _svc.async_refill_set, schema=REFILL_SET_SCHEMA)
        hass.services.async_register(DOMAIN, "refill_add", _svc.async_refill_add, schema=REFILL_ADD_SCHEMA)
        hass.services.async_register(DOMAIN, "refill_acknowledge", _svc.async_refill_acknowledge, schema=REFILL_ACK_SCHEMA)
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
            if not is_valid_medication_entity_id(entity_id):
                _LOGGER.warning("Ignoring mobile action with invalid entity_id: %s", entity_id)
                return
            entity = hass.data[DOMAIN]["entities"].get(entity_id)
            if not entity:
                return
            if action in ("MED_TAKEN", "TAKEN"):
                await entity.async_mark(STATE_TAKEN)
            elif action in ("MED_SKIP", "SKIP", "SKIPPED", "MED_DISMISS", "DISMISS"):
                await entity.async_mark(STATE_SKIPPED)
            elif action in ("MED_SNOOZE", "SNOOZE", "SNOOZED"):
                minutes = ad.get("minutes")
                try:
                    minutes = int(minutes) if minutes is not None else int(entity.snooze_minutes)
                except (TypeError, ValueError):
                    minutes = DEFAULT_SNOOZE_MINUTES
                minutes = max(1, min(1440, minutes))
                await entity.async_snooze(minutes)

        store["mobile_unsub"] = hass.bus.async_listen("mobile_app_notification_action", _handle_mobile_action)
        _LOGGER.debug("%s: listening for mobile_app_notification_action", DOMAIN)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to a newer version."""
    _LOGGER.info("Migrating %s entry from version %s", DOMAIN, entry.version)
    # No migrations needed yet — placeholder for future schema changes.
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
        for svc in ("mark_taken", "mark_skipped", "mark_snoozed", "mark_pending", "refill_set", "refill_add", "refill_acknowledge"):
            if hass.services.has_service(DOMAIN, svc):
                hass.services.async_remove(DOMAIN, svc)
        unsub = store.get("mobile_unsub")
        if unsub:
            try:
                unsub()
            except Exception:
                _LOGGER.debug("Error unsubscribing mobile listener", exc_info=True)
            store["mobile_unsub"] = None
        store.get("entities", {}).clear()
        store.pop("history", None)
        store["services_registered"] = False
    return True
