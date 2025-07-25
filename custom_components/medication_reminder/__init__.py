"""Medication Reminder integration for Home Assistant."""
import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_point_in_time

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, DEFAULT_SNOOZE_MINUTES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Medication Reminder from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    meds = await store.async_load() or []
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["meds"] = meds
    hass.data[DOMAIN]["store"] = store

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, "sensor"))
    _LOGGER.info("Loaded %d medications", len(meds))

    for med in meds:
        await schedule_med_reminders(hass, med)

    async def mark_taken(call: ServiceCall):
        await update_med_status(hass, call.data["entity_id"], "Taken")

    async def mark_skipped(call: ServiceCall):
        await update_med_status(hass, call.data["entity_id"], "Skipped")

    async def mark_snoozed(call: ServiceCall):
        await snooze_medication(hass, call.data["entity_id"])

    hass.services.async_register(DOMAIN, "mark_taken", mark_taken)
    hass.services.async_register(DOMAIN, "mark_skipped", mark_skipped)
    hass.services.async_register(DOMAIN, "mark_snoozed", mark_snoozed)
    return True

async def schedule_med_reminders(hass: HomeAssistant, med: dict):
    """Schedule reminders for a medication."""
    for time_str in med.get("times", []):
        now = datetime.now()
        target = now.replace(hour=int(time_str.split(":")[0]), minute=int(time_str.split(":")[1]), second=0)
        if target < now:
            target += timedelta(days=1)
        async_track_point_in_time(hass, lambda _: send_reminder(hass, med), target)

async def send_reminder(hass: HomeAssistant, med: dict):
    """Send a persistent notification."""
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": f"Medication Reminder: {med['name']}",
            "message": f"Time to take {med['dose']} ({med['name']})"
        }
    )

async def update_med_status(hass: HomeAssistant, entity_id: str, status: str):
    """Update medication status and log history."""
    meds = hass.data[DOMAIN]["meds"]
    for med in meds:
        if f"medication.{med['name'].lower().replace(' ', '_')}" == entity_id:
            med["last_action"] = {"status": status, "timestamp": datetime.now().isoformat()}
            await hass.data[DOMAIN]["store"].async_save(meds)
            _LOGGER.info("Updated %s to %s", med['name'], status)
            return

async def snooze_medication(hass: HomeAssistant, entity_id: str):
    """Snooze a medication reminder."""
    meds = hass.data[DOMAIN]["meds"]
    for med in meds:
        if f"medication.{med['name'].lower().replace(' ', '_')}" == entity_id:
            snooze_time = datetime.now() + timedelta(minutes=DEFAULT_SNOOZE_MINUTES)
            async_track_point_in_time(hass, lambda _: send_reminder(hass, med), snooze_time)
            med["last_action"] = {"status": "Snoozed", "timestamp": datetime.now().isoformat()}
            await hass.data[DOMAIN]["store"].async_save(meds)
            _LOGGER.info("Snoozed %s for %d minutes", med['name'], DEFAULT_SNOOZE_MINUTES)
            return
