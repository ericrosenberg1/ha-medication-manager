"""Sensor platform for Medication Reminder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, List, Optional

import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ATTR_DOSE,
    ATTR_LAST_ACTION,
    ATTR_NAME,
    ATTR_TIMES,
    DEFAULT_SNOOZE_MINUTES,
    STATE_PENDING,
    STATE_SNOOZED,
    SIGNAL_HISTORY_UPDATED,
)
from .history import HistoryManager


def _slugify(name: str) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in name.lower())
    return "_".join([p for p in base.split("_") if p])


def _parse_times(value: str | list[str]) -> list[str]:
    """Parse HH:MM or list of HH:MM values; return normalized list."""
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
    seen = set()
    unique: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    name: str = entry.data.get(ATTR_NAME) or entry.title or "Medication"
    dose: str = (entry.options.get(ATTR_DOSE) or entry.data.get(ATTR_DOSE) or "").strip()
    times_raw = entry.options.get(ATTR_TIMES) or entry.data.get(ATTR_TIMES) or []
    times = _parse_times(times_raw) if isinstance(times_raw, str) else list(times_raw)

    snooze_minutes = int(entry.options.get("snooze_minutes", DEFAULT_SNOOZE_MINUTES))
    notify_services_raw = (entry.options.get("notify_services") or "").strip()
    notify_services = [s.strip() for s in notify_services_raw.split(",") if s.strip()]

    med_entity = MedicationSensor(
        hass=hass,
        name=name,
        dose=dose,
        times=times,
        snooze_minutes=snooze_minutes,
        notify_services=notify_services,
        entry_id=entry.entry_id,
    )

    history: HistoryManager = hass.data[DOMAIN]["history"]
    hist_entity = MedicationAdherenceSensor(
        hass=hass,
        name=name,
        times=times,
        history=history,
        source_entity_id=None,  # Will be filled after med_entity has entity_id
        slug=_slugify(name),
    )

    # Link adherence sensor to the medication entity
    hist_entity.set_source_entity_id(med_entity.entity_id)
    async_add_entities([med_entity, hist_entity])

    async def _options_updated(hass: HomeAssistant, updated_entry: ConfigEntry):
        new_dose = (updated_entry.options.get(ATTR_DOSE) or updated_entry.data.get(ATTR_DOSE) or "").strip()
        new_times_raw = updated_entry.options.get(ATTR_TIMES) or updated_entry.data.get(ATTR_TIMES) or []
        new_times = (
            _parse_times(new_times_raw) if isinstance(new_times_raw, str) else list(new_times_raw)
        )
        new_snooze = int(updated_entry.options.get("snooze_minutes", DEFAULT_SNOOZE_MINUTES))
        new_notify_raw = (updated_entry.options.get("notify_services") or "").strip()
        new_notify = [s.strip() for s in new_notify_raw.split(",") if s.strip()]
        med_entity.update_config(dose=new_dose, times=new_times, snooze_minutes=new_snooze, notify_services=new_notify)
        hist_entity.update_times(new_times)

    entry.async_on_unload(entry.add_update_listener(_options_updated))


@dataclass
class _LastAction:
    status: str
    timestamp: str


class MedicationSensor(SensorEntity):
    """Represents a medication as a sensor entity."""

    _attr_icon = "mdi:pill"

    def __init__(self, hass: HomeAssistant, name: str, dose: str, times: list[str], snooze_minutes: int, notify_services: list[str], entry_id: str):
        self.hass = hass
        self._name = name
        self._dose = dose
        self._times = times
        self._state = STATE_PENDING
        self._last_action: Optional[_LastAction] = None
        self._unsubs: list[Callable[[], None]] = []
        self._snooze_minutes = snooze_minutes
        self._notify_services = notify_services
        self._entry_id = entry_id

        slug = _slugify(name)
        self._attr_name = name
        self._attr_unique_id = f"med_{slug}"
        # Stable entity_id for ease of use and card compatibility
        self.entity_id = f"sensor.medication_{slug}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "medication_reminder")},
            "name": "Medication Reminder",
            "manufacturer": "Local",
        }

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            ATTR_NAME: self._name,
            ATTR_DOSE: self._dose,
            ATTR_TIMES: self._times,
            ATTR_LAST_ACTION: None
            if not self._last_action
            else {"status": self._last_action.status, "timestamp": self._last_action.timestamp},
        }

    async def async_added_to_hass(self) -> None:
        # Register in shared mapping so services can find us by entity_id
        self.hass.data.setdefault(DOMAIN, {}).setdefault("entities", {})[self.entity_id] = self
        self._schedule_all()

    async def async_will_remove_from_hass(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        self.hass.data.get(DOMAIN, {}).get("entities", {}).pop(self.entity_id, None)

    def _schedule_all(self) -> None:
        # Cancel any existing schedules
        for u in self._unsubs:
            u()
        self._unsubs.clear()

        now = dt_util.now()
        for t in self._times:
            hh, mm = (int(x) for x in t.split(":"))
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)

            def _cb(_, hhi=hh, mmi=mm):
                self.hass.async_create_task(self._async_send_reminder())
                # After firing, schedule next day's reminder for this time
                self._reschedule_time(hhi, mmi)

            unsub = async_track_point_in_time(self.hass, _cb, target)
            self._unsubs.append(unsub)

    def _reschedule_time(self, hh: int, mm: int) -> None:
        next_time = dt_util.now().replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(days=1)

        def _cb(_, hhi=hh, mmi=mm):
            self.hass.async_create_task(self._async_send_reminder())
            self._reschedule_time(hhi, mmi)

        unsub = async_track_point_in_time(self.hass, _cb, next_time)
        self._unsubs.append(unsub)

    async def _async_send_reminder(self) -> None:
        message = f"Time to take {self._dose} ({self._name})"
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {"title": f"Medication Reminder: {self._name}", "message": message},
            blocking=False,
        )
        # Mobile actionable notification(s)
        if self._notify_services:
            actions = [
                {"action": "MED_TAKEN", "title": "Taken"},
                {"action": "MED_SKIP", "title": "Skip"},
                {"action": "MED_SNOOZE", "title": f"Snooze ({self._snooze_minutes}m)"},
            ]
            data = {
                "tag": self.entity_id,
                "actions": actions,
                "action_data": {"entity_id": self.entity_id, "minutes": self._snooze_minutes},
            }
            for svc in self._notify_services:
                svc = svc.strip()
                if not svc:
                    continue
                # Allow both 'notify.mobile_app_*' and 'mobile_app_*'
                if svc.startswith("notify."):
                    domain, service = svc.split(".", 1)
                else:
                    domain, service = "notify", svc
                await self.hass.services.async_call(
                    domain,
                    service,
                    {"title": f"Medication Reminder: {self._name}", "message": message, "data": data},
                    blocking=False,
                )
        # Do not change state automatically; keep Pending until user acts
        self._last_action = _LastAction(status="Reminder", timestamp=dt_util.now().isoformat())
        self.async_write_ha_state()

    async def async_mark(self, status: str) -> None:
        self._state = status
        self._last_action = _LastAction(status=status, timestamp=dt_util.now().isoformat())
        self.async_write_ha_state()

    async def async_snooze(self, minutes: int = DEFAULT_SNOOZE_MINUTES) -> None:
        when = dt_util.now() + timedelta(minutes=minutes)

        def _cb(_):
            self.hass.async_create_task(self._async_send_reminder())

        unsub = async_track_point_in_time(self.hass, _cb, when)
        self._unsubs.append(unsub)
        self._state = STATE_SNOOZED
        self._last_action = _LastAction(status=STATE_SNOOZED, timestamp=dt_util.now().isoformat())
        self.async_write_ha_state()

    @property
    def snooze_minutes(self) -> int:
        return self._snooze_minutes

    @callback
    def update_config(self, *, dose: Optional[str] = None, times: Optional[list[str]] = None, snooze_minutes: Optional[int] = None, notify_services: Optional[List[str]] = None) -> None:
        changed = False
        if dose is not None and dose != self._dose:
            self._dose = dose
            changed = True
        if times is not None and times != self._times:
            self._times = times
            changed = True
            self._schedule_all()
        if snooze_minutes is not None and snooze_minutes != self._snooze_minutes:
            self._snooze_minutes = snooze_minutes
            changed = True
        if notify_services is not None:
            self._notify_services = notify_services
            changed = True
        if changed:
            self.async_write_ha_state()


class MedicationAdherenceSensor(SensorEntity):
    """Adherence sensor showing 7-day adherence percent and recent events."""

    _attr_icon = "mdi:chart-line"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass: HomeAssistant, name: str, times: list[str], history: HistoryManager, source_entity_id: Optional[str], slug: str):
        self.hass = hass
        self._name = name
        self._times = times
        self._history = history
        self._source_entity_id = source_entity_id
        self._slug = slug
        self._state: Optional[float] = None
        self._attr_name = f"{name} Adherence"
        self._attr_unique_id = f"med_{slug}_adherence"
        self.entity_id = f"sensor.medication_{slug}_adherence"
        self._unsub_dispatcher = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "medication_reminder")},
            "name": "Medication Reminder",
            "manufacturer": "Local",
        }

    def set_source_entity_id(self, entity_id: str) -> None:
        self._source_entity_id = entity_id

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        if not self._source_entity_id:
            return {}
        recent = self._history.recent(self._source_entity_id, 20)
        counts, expected = self._compute_counts()
        return {
            "taken_7d": counts.get("taken", 0),
            "skipped_7d": counts.get("skipped", 0),
            "snoozed_7d": counts.get("snoozed", 0),
            "expected_7d": expected,
            "recent_events": recent,
        }

    def _compute_counts(self):
        if not self._source_entity_id:
            return {"taken": 0, "skipped": 0, "snoozed": 0}, 0
        days = 7
        expected = days * len(self._times or [])
        since = dt_util.now() - timedelta(days=days)
        counts = self._history.counts_since(self._source_entity_id, since)
        # adherence percent
        self._state = None if expected == 0 else round((counts.get("taken", 0) / expected) * 100)
        return counts, expected

    async def async_added_to_hass(self) -> None:
        @callback
        def _updated(entity_id: str):
            if self._source_entity_id and entity_id == self._source_entity_id:
                self._compute_counts()
                self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(self.hass, SIGNAL_HISTORY_UPDATED, _updated)
        # Initial compute
        self._compute_counts()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @callback
    def update_times(self, times: list[str]) -> None:
        self._times = times
        self._compute_counts()
        self.async_write_ha_state()
