"""Sensor platform for Medication Reminder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable
import logging
import re

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time, async_call_later
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity import async_generate_entity_id, DeviceInfo

from .const import (
    DOMAIN,
    ATTR_DOSE,
    ATTR_LAST_ACTION,
    ATTR_NAME,
    ATTR_TIMES,
    DEFAULT_SNOOZE_MINUTES,
    EVENT_STATE_CHANGED,
    STATE_PENDING,
    STATE_SNOOZED,
    STATE_TAKEN,
    STATE_SKIPPED,
    SIGNAL_HISTORY_UPDATED,
)
from .helpers import slugify, parse_times
from .history import HistoryManager

_LOGGER = logging.getLogger(__name__)


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD in HA's configured timezone."""
    return dt_util.now().strftime("%Y-%m-%d")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    name: str = entry.data.get(ATTR_NAME) or entry.title or "Medication"
    dose: str = (entry.options.get(ATTR_DOSE) or entry.data.get(ATTR_DOSE) or "").strip()
    times_raw = entry.options.get(ATTR_TIMES) or entry.data.get(ATTR_TIMES) or []
    times = parse_times(times_raw) if isinstance(times_raw, str) else list(times_raw)

    snooze_minutes = int(entry.options.get("snooze_minutes", DEFAULT_SNOOZE_MINUTES))
    notify_services_raw = (entry.options.get("notify_services") or "").strip()
    raw_services = [s.strip() for s in notify_services_raw.split(",") if s.strip()]

    def _sanitize_services(services: list[str]) -> list[str]:
        """Allow 'notify.xxx' or 'xxx'; return normalized unique list of 'xxx'."""
        out: list[str] = []
        seen: set[str] = set()
        pat = re.compile(r"^(?:notify\.)?[a-z0-9_]+$")
        for svc in services:
            if not pat.fullmatch(svc):
                continue
            svc_name = svc.split(".", 1)[1] if svc.startswith("notify.") else svc
            if svc_name not in seen:
                seen.add(svc_name)
                out.append(svc_name)
        return out

    notify_services = _sanitize_services(raw_services)

    nag_interval = int(entry.options.get("nag_interval_minutes", 5))
    nag_max = int(entry.options.get("nag_max", 3))
    refill_total = int(entry.options.get("refill_total", 0))
    refill_threshold = int(entry.options.get("refill_threshold", 0))
    units_per_intake = int(entry.options.get("dose_units_per_intake", 1))

    med_entity = MedicationSensor(
        hass=hass,
        name=name,
        dose=dose,
        times=times,
        snooze_minutes=snooze_minutes,
        notify_services=notify_services,
        nag_interval=nag_interval,
        nag_max=nag_max,
        refill_total=refill_total,
        refill_threshold=refill_threshold,
        units_per_intake=units_per_intake,
        entry_id=entry.entry_id,
    )

    history: HistoryManager = hass.data[DOMAIN]["history"]
    hist_entity = MedicationAdherenceSensor(
        hass=hass,
        name=name,
        times=times,
        history=history,
        source_entity_id=None,
        slug=slugify(name),
    )

    stats_entity = MedicationStatsSensor(
        hass=hass,
        name=name,
        times=times,
        history=history,
        source_entity_id=None,
        slug=slugify(name),
    )

    # Link adherence sensor to the medication entity
    hist_entity.set_source_entity_id(med_entity.entity_id)
    stats_entity.set_source_entity_id(med_entity.entity_id)
    async_add_entities([med_entity, hist_entity, stats_entity])

    async def _options_updated(hass: HomeAssistant, updated_entry: ConfigEntry):
        new_dose = (updated_entry.options.get(ATTR_DOSE) or updated_entry.data.get(ATTR_DOSE) or "").strip()
        new_times_raw = updated_entry.options.get(ATTR_TIMES) or updated_entry.data.get(ATTR_TIMES) or []
        new_times = (
            parse_times(new_times_raw) if isinstance(new_times_raw, str) else list(new_times_raw)
        )
        new_snooze = int(updated_entry.options.get("snooze_minutes", DEFAULT_SNOOZE_MINUTES))
        new_notify_raw = (updated_entry.options.get("notify_services") or "").strip()
        new_notify = [s.strip() for s in new_notify_raw.split(",") if s.strip()]
        new_nag_interval = int(updated_entry.options.get("nag_interval_minutes", 5))
        new_nag_max = int(updated_entry.options.get("nag_max", 3))
        new_units = int(updated_entry.options.get("dose_units_per_intake", 1))
        new_refill_total = int(updated_entry.options.get("refill_total", 0))
        new_refill_threshold = int(updated_entry.options.get("refill_threshold", 0))
        med_entity.update_config(
            dose=new_dose,
            times=new_times,
            snooze_minutes=new_snooze,
            notify_services=new_notify,
            nag_interval=new_nag_interval,
            nag_max=new_nag_max,
            units_per_intake=new_units,
            refill_total=new_refill_total,
            refill_threshold=new_refill_threshold,
        )
        hist_entity.update_times(new_times)
        stats_entity.update_times(new_times)

    entry.async_on_unload(entry.add_update_listener(_options_updated))


@dataclass
class _LastAction:
    status: str
    timestamp: str


class MedicationSensor(SensorEntity):
    """Represents a medication as a sensor entity."""

    _attr_icon = "mdi:pill"

    def __init__(self, hass: HomeAssistant, name: str, dose: str, times: list[str], snooze_minutes: int, notify_services: list[str], nag_interval: int, nag_max: int, refill_total: int, refill_threshold: int, units_per_intake: int, entry_id: str):
        self.hass = hass
        self._name = name
        self._dose = dose
        self._times = times
        self._state = STATE_PENDING
        self._last_action: _LastAction | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._snooze_minutes = snooze_minutes
        self._notify_services = notify_services
        self._nag_interval = max(0, int(nag_interval))
        self._nag_max = max(0, int(nag_max))
        self._nag_remaining = 0
        self._nag_unsub: Callable[[], None] | None = None
        self._units_per_intake = max(1, int(units_per_intake))
        self._refill_threshold = max(0, int(refill_threshold))
        self._init_refill_total = max(0, int(refill_total))
        self._entry_id = entry_id
        self._midnight_unsub: Callable[[], None] | None = None

        slug = slugify(name)
        self._attr_name = name
        self._attr_unique_id = f"med_{slug}"
        self.entity_id = async_generate_entity_id("sensor.{}", f"medication_{slug}", hass=hass)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "medication_reminder")},
            name="Medication Reminder",
        )

    @property
    def native_value(self):
        return self._state

    @property
    def icon(self):
        st = str(self._state or "").lower()
        if st.startswith("take"):
            return "mdi:check-circle"
        if st.startswith("skip"):
            return "mdi:close-circle"
        if st.startswith("snooz"):
            return "mdi:alarm-snooze"
        return "mdi:pill"

    @property
    def extra_state_attributes(self):
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        refill = history.get_refill(self.entity_id) or {}
        return {
            ATTR_NAME: self._name,
            ATTR_DOSE: self._dose,
            ATTR_TIMES: self._times,
            "snooze_minutes": self._snooze_minutes,
            "notify_services": [f"notify.{s}" for s in self._notify_services],
            "nag_interval_minutes": self._nag_interval,
            "nag_max": self._nag_max,
            "refill_remaining": refill.get("remaining"),
            "refill_threshold": refill.get("threshold"),
            "units_per_intake": refill.get("units_per_intake", self._units_per_intake),
            "refill_needed": bool(refill.get("alerted", False)) if refill else False,
            ATTR_LAST_ACTION: None
            if not self._last_action
            else {"status": self._last_action.status, "timestamp": self._last_action.timestamp},
        }

    async def async_added_to_hass(self) -> None:
        # Register in shared mapping so services can find us by entity_id
        self.hass.data.setdefault(DOMAIN, {}).setdefault("entities", {})[self.entity_id] = self

        # Initialize refill persistence (from options if present and nothing stored yet)
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        info = history.get_refill(self.entity_id)
        if info is None and (self._init_refill_total > 0 or self._refill_threshold > 0):
            await history.set_refill(self.entity_id, remaining=self._init_refill_total, threshold=self._refill_threshold, units_per_intake=self._units_per_intake)

        # Restore state from persistence
        await self._restore_state()

        # Schedule reminders and midnight reset
        self._schedule_all()
        self._schedule_midnight_reset()

        # Recover any active snooze
        await self._recover_snooze()

    async def _restore_state(self) -> None:
        """Restore last known state on startup. Reset to Pending if it's a new day."""
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        saved = history.get_last_state(self.entity_id)
        if not saved:
            return
        saved_date = saved.get("date", "")
        today = _today_str()
        if saved_date == today:
            # Same day: restore the saved state
            self._state = saved.get("state", STATE_PENDING)
            ts = saved.get("timestamp")
            if ts:
                self._last_action = _LastAction(status=self._state, timestamp=ts)
        else:
            # New day: reset to Pending
            self._state = STATE_PENDING
            self._last_action = None

    async def _recover_snooze(self) -> None:
        """On startup, check if there's an active snooze to resume."""
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        snooze_iso = history.get_snooze_until(self.entity_id)
        if not snooze_iso:
            return
        snooze_time = dt_util.parse_datetime(snooze_iso)
        if snooze_time is None:
            await history.set_snooze_until(self.entity_id, None)
            return
        now = dt_util.now()
        if snooze_time > now:
            # Snooze still active, re-schedule
            self._state = STATE_SNOOZED
            self._last_action = _LastAction(status=STATE_SNOOZED, timestamp=snooze_iso)
            self.async_write_ha_state()

            def _cb(_):
                self.hass.async_create_task(self._snooze_expired())

            unsub = async_track_point_in_time(self.hass, _cb, snooze_time)
            self._unsubs.append(unsub)
            _LOGGER.debug("%s: restored snooze until %s", self.entity_id, snooze_iso)
        else:
            # Snooze expired while we were down, fire reminder now
            await history.set_snooze_until(self.entity_id, None)
            _LOGGER.debug("%s: snooze expired during downtime, firing reminder", self.entity_id)
            await self._async_send_reminder()

    async def _snooze_expired(self) -> None:
        """Called when a recovered or new snooze timer expires."""
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        await history.set_snooze_until(self.entity_id, None)
        await self._async_send_reminder()

    async def async_will_remove_from_hass(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        if self._nag_unsub:
            self._nag_unsub()
            self._nag_unsub = None
        if self._midnight_unsub:
            self._midnight_unsub()
            self._midnight_unsub = None
        self.hass.data.get(DOMAIN, {}).get("entities", {}).pop(self.entity_id, None)

    def _schedule_all(self) -> None:
        """Schedule reminders for each configured time, with restart recovery."""
        # Cancel any existing schedules
        for u in self._unsubs:
            u()
        self._unsubs.clear()

        now = dt_util.now()
        today = _today_str()
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        last_reminded = history.get_last_reminded(self.entity_id)

        for t in self._times:
            hh, mm = (int(x) for x in t.split(":"))
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)

            # Check if this slot already fired today
            slot_last_date = last_reminded.get(t, "")

            if target <= now:
                if slot_last_date != today:
                    # This slot's time has passed today but never fired.
                    # Only fire catch-up if the state is still Pending (user hasn't acted yet)
                    if self._state == STATE_PENDING:
                        _LOGGER.info(
                            "%s: catch-up reminder for missed slot %s",
                            self.entity_id, t,
                        )
                        self.hass.async_create_task(self._fire_slot(t))
                # Schedule for tomorrow regardless
                target += timedelta(days=1)
            # else: target is in the future today, schedule normally

            def _cb(_, hhi=hh, mmi=mm, slot=t):
                self.hass.async_create_task(self._fire_slot(slot))
                self._reschedule_time(hhi, mmi, slot)

            unsub = async_track_point_in_time(self.hass, _cb, target)
            self._unsubs.append(unsub)

    async def _fire_slot(self, time_slot: str) -> None:
        """Fire a reminder for a specific time slot and record it."""
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        await history.set_last_reminded(self.entity_id, time_slot, _today_str())
        await self._async_send_reminder()

    def _reschedule_time(self, hh: int, mm: int, time_slot: str) -> None:
        next_time = dt_util.now().replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(days=1)

        def _cb(_, hhi=hh, mmi=mm, slot=time_slot):
            self.hass.async_create_task(self._fire_slot(slot))
            self._reschedule_time(hhi, mmi, slot)

        unsub = async_track_point_in_time(self.hass, _cb, next_time)
        self._unsubs.append(unsub)

    def _schedule_midnight_reset(self) -> None:
        """Schedule a daily reset to Pending at midnight."""
        if self._midnight_unsub:
            self._midnight_unsub()
            self._midnight_unsub = None

        now = dt_util.now()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        def _cb(_):
            self.hass.async_create_task(self._async_midnight_reset())

        self._midnight_unsub = async_track_point_in_time(self.hass, _cb, midnight)

    async def _async_midnight_reset(self) -> None:
        """Reset state to Pending at midnight and reschedule."""
        old_state = self._state
        self._state = STATE_PENDING
        self._last_action = None
        self._cancel_nags()
        self.async_write_ha_state()

        # Persist the reset
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        await history.set_last_state(self.entity_id, STATE_PENDING, dt_util.now().isoformat(), _today_str())
        await history.set_snooze_until(self.entity_id, None)

        # Fire event for automations
        if old_state != STATE_PENDING:
            self.hass.bus.async_fire(EVENT_STATE_CHANGED, {
                "entity_id": self.entity_id,
                "old_state": old_state,
                "new_state": STATE_PENDING,
                "timestamp": dt_util.now().isoformat(),
            })

        # Reschedule midnight for next day
        self._schedule_midnight_reset()

        _LOGGER.debug("%s: midnight reset to Pending", self.entity_id)

    async def _async_send_reminder(self) -> None:
        message = f"Time to take {self._dose} ({self._name})" if self._dose else f"Time to take {self._name}"
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {"title": f"Medication Reminder: {self._name}", "message": message},
                blocking=False,
            )
        except Exception:
            _LOGGER.warning("%s: failed to create persistent notification", self.entity_id)

        # Mobile actionable notification(s)
        if self._notify_services:
            actions = [
                {"action": "MED_TAKEN", "title": "Taken"},
                {"action": "MED_SKIP", "title": "Skip"},
                {"action": "MED_SNOOZE", "title": f"Snooze ({self._snooze_minutes}m)"},
                {"action": "MED_DISMISS", "title": "Dismiss"},
            ]
            data = {
                "tag": self.entity_id,
                "actions": actions,
                "action_data": {"entity_id": self.entity_id, "minutes": self._snooze_minutes},
            }
            for service in self._notify_services:
                try:
                    await self.hass.services.async_call(
                        "notify",
                        service,
                        {"title": f"Medication Reminder: {self._name}", "message": message, "data": data},
                        blocking=False,
                    )
                except Exception:
                    _LOGGER.warning("%s: failed to call notify.%s", self.entity_id, service)

        self._last_action = _LastAction(status="Reminder", timestamp=dt_util.now().isoformat())
        self.async_write_ha_state()
        self._start_nags()

    async def async_mark(self, status: str) -> None:
        old_state = self._state
        self._state = status
        now_iso = dt_util.now().isoformat()
        self._last_action = _LastAction(status=status, timestamp=now_iso)
        self.async_write_ha_state()
        self._cancel_nags()

        # Persist state for restart recovery
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        await history.set_last_state(self.entity_id, status, now_iso, _today_str())

        # Clear snooze on any explicit action
        if status != STATE_SNOOZED:
            await history.set_snooze_until(self.entity_id, None)

        if status.lower().startswith("take"):
            await self._handle_refill_after_taken()

        # Record to history (so callers don't need to duplicate this)
        await history.record(self.entity_id, status, now_iso)

        # Fire HA event for automations
        if old_state != status:
            self.hass.bus.async_fire(EVENT_STATE_CHANGED, {
                "entity_id": self.entity_id,
                "old_state": old_state,
                "new_state": status,
                "timestamp": now_iso,
            })

    async def async_snooze(self, minutes: int = DEFAULT_SNOOZE_MINUTES) -> None:
        when = dt_util.now() + timedelta(minutes=minutes)

        # Persist snooze for restart recovery
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        await history.set_snooze_until(self.entity_id, when.isoformat())

        def _cb(_):
            self.hass.async_create_task(self._snooze_expired())

        unsub = async_track_point_in_time(self.hass, _cb, when)
        self._unsubs.append(unsub)

        old_state = self._state
        self._state = STATE_SNOOZED
        now_iso = dt_util.now().isoformat()
        self._last_action = _LastAction(status=STATE_SNOOZED, timestamp=now_iso)
        self.async_write_ha_state()
        self._cancel_nags()

        # Persist state
        await history.set_last_state(self.entity_id, STATE_SNOOZED, now_iso, _today_str())

        # Record to history (so callers don't need to duplicate this)
        await history.record(self.entity_id, "Snoozed", now_iso)

        # Fire event
        if old_state != STATE_SNOOZED:
            self.hass.bus.async_fire(EVENT_STATE_CHANGED, {
                "entity_id": self.entity_id,
                "old_state": old_state,
                "new_state": STATE_SNOOZED,
                "timestamp": now_iso,
            })

    @property
    def snooze_minutes(self) -> int:
        return self._snooze_minutes

    @callback
    def update_config(self, *, dose: str | None = None, times: list[str] | None = None, snooze_minutes: int | None = None, notify_services: list[str] | None = None, nag_interval: int | None = None, nag_max: int | None = None, units_per_intake: int | None = None, refill_total: int | None = None, refill_threshold: int | None = None) -> None:
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
            pat = re.compile(r"^[a-z0-9_]+$")
            self._notify_services = [s for s in notify_services if pat.fullmatch(s)]
            changed = True
        if nag_interval is not None and nag_interval != self._nag_interval:
            self._nag_interval = max(0, int(nag_interval))
            changed = True
        if nag_max is not None and nag_max != self._nag_max:
            self._nag_max = max(0, int(nag_max))
            changed = True
        if units_per_intake is not None and units_per_intake != self._units_per_intake:
            self._units_per_intake = max(1, int(units_per_intake))
            changed = True
        if refill_threshold is not None and refill_threshold != self._refill_threshold:
            self._refill_threshold = max(0, int(refill_threshold))
            changed = True
        if refill_total is not None:
            hist: HistoryManager = self.hass.data[DOMAIN]["history"]
            self.hass.async_create_task(hist.adjust_refill(self.entity_id, remaining=max(0, int(refill_total))))
            changed = True
        if changed:
            self.async_write_ha_state()

    def _cancel_nags(self) -> None:
        if self._nag_unsub:
            try:
                self._nag_unsub()
            except Exception:
                pass
            self._nag_unsub = None
        self._nag_remaining = 0

    def _start_nags(self) -> None:
        self._cancel_nags()
        if self._nag_interval <= 0 or self._nag_max <= 0:
            return
        self._nag_remaining = self._nag_max

        def _nag_cb(_):
            st = str(self._state or "").lower()
            if st.startswith("take") or st.startswith("skip"):
                self._cancel_nags()
                return
            self.hass.async_create_task(self._async_send_reminder())
            self._nag_remaining -= 1
            if self._nag_remaining <= 0:
                self._cancel_nags()
                return
            self._nag_unsub = async_call_later(self.hass, self._nag_interval * 60, _nag_cb)

        self._nag_unsub = async_call_later(self.hass, self._nag_interval * 60, _nag_cb)

    async def _handle_refill_after_taken(self) -> None:
        hist: HistoryManager = self.hass.data[DOMAIN]["history"]
        info = hist.get_refill(self.entity_id)
        if not info:
            return
        updated = await hist.decrement_refill(self.entity_id, self._units_per_intake)
        if not updated:
            return
        if int(updated.get("remaining", 0)) <= int(updated.get("threshold", 0)) and not bool(updated.get("alerted", False)):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"Medication Refill: {self._name}",
                    "message": f"{self._name}: Remaining {updated.get('remaining')} ≤ threshold {updated.get('threshold')}. Please refill.",
                },
                blocking=False,
            )
            await hist.adjust_refill(self.entity_id, alerted=True)


class MedicationAdherenceSensor(SensorEntity):
    """Adherence sensor showing 7-day adherence percent and recent events."""

    _attr_icon = "mdi:chart-line"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, name: str, times: list[str], history: HistoryManager, source_entity_id: str | None, slug: str):
        self.hass = hass
        self._name = name
        self._times = times
        self._history = history
        self._source_entity_id = source_entity_id
        self._slug = slug
        self._state: float | None = None
        self._attr_name = f"{name} Adherence"
        self._attr_unique_id = f"med_{slug}_adherence"
        self.entity_id = async_generate_entity_id("sensor.{}", f"medication_{slug}_adherence", hass=hass)
        self._unsub_dispatcher = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "medication_reminder")},
            name="Medication Reminder",
        )

    def set_source_entity_id(self, entity_id: str) -> None:
        self._source_entity_id = entity_id

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        if not self._source_entity_id:
            return {}
        recent = self._history.recent(self._source_entity_id, 100)
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
        self._state = None if expected == 0 else round((counts.get("taken", 0) / expected) * 100)
        return counts, expected

    async def async_added_to_hass(self) -> None:
        @callback
        def _updated(entity_id: str):
            if self._source_entity_id and entity_id == self._source_entity_id:
                self._compute_counts()
                self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(self.hass, SIGNAL_HISTORY_UPDATED, _updated)
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


class MedicationStatsSensor(SensorEntity):
    """Statistics sensor with daily/weekly/monthly/yearly taken/skipped/missed counts."""

    _attr_icon = "mdi:table"

    def __init__(self, hass: HomeAssistant, name: str, times: list[str], history: HistoryManager, source_entity_id: str | None, slug: str):
        self.hass = hass
        self._name = name
        self._times = times
        self._history = history
        self._source_entity_id = source_entity_id
        self._slug = slug
        self._state: int | None = None
        self._attr_name = f"{name} Stats"
        self._attr_unique_id = f"med_{slug}_stats"
        self.entity_id = async_generate_entity_id("sensor.{}", f"medication_{slug}_stats", hass=hass)
        self._unsub_dispatcher = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "medication_reminder")},
            name="Medication Reminder",
        )

    def set_source_entity_id(self, entity_id: str) -> None:
        self._source_entity_id = entity_id

    def _period_counts(self, days: int):
        if not self._source_entity_id:
            return {"taken": 0, "skipped": 0, "missed": 0, "expected": 0}
        now = dt_util.now()
        start = now - timedelta(days=days)
        counts = self._history.counts_between(self._source_entity_id, start, now)
        expected = days * len(self._times or [])
        missed = max(0, expected - counts.get("taken", 0) - counts.get("skipped", 0))
        return {"taken": counts.get("taken", 0), "skipped": counts.get("skipped", 0), "missed": missed, "expected": expected}

    @property
    def native_value(self):
        data = self._period_counts(30)
        exp = data.get("expected", 0)
        self._state = None if exp == 0 else round((data.get("taken", 0) / exp) * 100)
        return self._state

    @property
    def extra_state_attributes(self):
        daily = self._period_counts(1)
        weekly = self._period_counts(7)
        monthly = self._period_counts(30)
        yearly = self._period_counts(365)
        return {
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
            "yearly": yearly,
        }

    async def async_added_to_hass(self) -> None:
        @callback
        def _updated(entity_id: str):
            if self._source_entity_id and entity_id == self._source_entity_id:
                self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(self.hass, SIGNAL_HISTORY_UPDATED, _updated)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @callback
    def update_times(self, times: list[str]) -> None:
        self._times = times
        self.async_write_ha_state()
