"""Sensor platform for Medication Reminder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, List, Optional
import re

import voluptuous as vol

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time, async_call_later
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity import async_generate_entity_id

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
    raw_services = [s.strip() for s in notify_services_raw.split(",") if s.strip()]

    def _sanitize_services(services: List[str]) -> List[str]:
        """Allow 'notify.xxx' or 'xxx'; return normalized unique list of 'xxx'."""
        out: list[str] = []
        seen: set[str] = set()
        pat = re.compile(r"^(?:notify\.)?[a-z0-9_]+$")
        for svc in services:
            if not pat.fullmatch(svc):
                continue
            name = svc.split(".", 1)[1] if svc.startswith("notify.") else svc
            if name not in seen:
                seen.add(name)
                out.append(name)
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
        source_entity_id=None,  # Will be filled after med_entity has entity_id
        slug=_slugify(name),
    )

    stats_entity = MedicationStatsSensor(
        hass=hass,
        name=name,
        times=times,
        history=history,
        source_entity_id=None,  # Set after med_entity created
        slug=_slugify(name),
    )

    # Link adherence sensor to the medication entity
    hist_entity.set_source_entity_id(med_entity.entity_id)
    stats_entity.set_source_entity_id(med_entity.entity_id)
    async_add_entities([med_entity, hist_entity, stats_entity])

    async def _options_updated(hass: HomeAssistant, updated_entry: ConfigEntry):
        new_dose = (updated_entry.options.get(ATTR_DOSE) or updated_entry.data.get(ATTR_DOSE) or "").strip()
        new_times_raw = updated_entry.options.get(ATTR_TIMES) or updated_entry.data.get(ATTR_TIMES) or []
        new_times = (
            _parse_times(new_times_raw) if isinstance(new_times_raw, str) else list(new_times_raw)
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
        self._last_action: Optional[_LastAction] = None
        self._unsubs: list[Callable[[], None]] = []
        self._snooze_minutes = snooze_minutes
        self._notify_services = notify_services
        self._nag_interval = max(0, int(nag_interval))
        self._nag_max = max(0, int(nag_max))
        self._nag_remaining = 0
        self._nag_unsub: Optional[Callable[[], None]] = None
        self._units_per_intake = max(1, int(units_per_intake))
        self._refill_threshold = max(0, int(refill_threshold))
        self._init_refill_total = max(0, int(refill_total))
        self._entry_id = entry_id

        slug = _slugify(name)
        self._attr_name = name
        self._attr_unique_id = f"med_{slug}"
        # Stable entity_id using HA helper; remains sensor.medication_<slug> when free
        self.entity_id = async_generate_entity_id("sensor.{}", f"medication_{slug}", hass=hass)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "medication_reminder")},
            "name": "Medication Reminder",
        }

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
        self._schedule_all()
        # Initialize refill persistence (from options if present and nothing stored yet)
        history: HistoryManager = self.hass.data[DOMAIN]["history"]
        info = history.get_refill(self.entity_id)
        if info is None and (self._init_refill_total > 0 or self._refill_threshold > 0):
            await history.set_refill(self.entity_id, remaining=self._init_refill_total, threshold=self._refill_threshold, units_per_intake=self._units_per_intake)

    async def async_will_remove_from_hass(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        if self._nag_unsub:
            self._nag_unsub()
            self._nag_unsub = None
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
                {"action": "MED_DISMISS", "title": "Dismiss"},
            ]
            data = {
                "tag": self.entity_id,
                "actions": actions,
                "action_data": {"entity_id": self.entity_id, "minutes": self._snooze_minutes},
            }
            for service in self._notify_services:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"title": f"Medication Reminder: {self._name}", "message": message, "data": data},
                    blocking=False,
                )
        # Do not change state automatically; keep Pending until user acts
        self._last_action = _LastAction(status="Reminder", timestamp=dt_util.now().isoformat())
        self.async_write_ha_state()
        self._start_nags()

    async def async_mark(self, status: str) -> None:
        self._state = status
        self._last_action = _LastAction(status=status, timestamp=dt_util.now().isoformat())
        self.async_write_ha_state()
        # Cancel nags on any explicit action
        self._cancel_nags()
        if status.lower().startswith("take"):
            await self._handle_refill_after_taken()

    async def async_snooze(self, minutes: int = DEFAULT_SNOOZE_MINUTES) -> None:
        when = dt_util.now() + timedelta(minutes=minutes)

        def _cb(_):
            self.hass.async_create_task(self._async_send_reminder())

        unsub = async_track_point_in_time(self.hass, _cb, when)
        self._unsubs.append(unsub)
        self._state = STATE_SNOOZED
        self._last_action = _LastAction(status=STATE_SNOOZED, timestamp=dt_util.now().isoformat())
        self.async_write_ha_state()
        self._cancel_nags()

    @property
    def snooze_minutes(self) -> int:
        return self._snooze_minutes

    @callback
    def update_config(self, *, dose: Optional[str] = None, times: Optional[list[str]] = None, snooze_minutes: Optional[int] = None, notify_services: Optional[List[str]] = None, nag_interval: Optional[int] = None, nag_max: Optional[int] = None, units_per_intake: Optional[int] = None, refill_total: Optional[int] = None, refill_threshold: Optional[int] = None) -> None:
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
        self.entity_id = async_generate_entity_id("sensor.{}", f"medication_{slug}_adherence", hass=hass)
        self._unsub_dispatcher = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "medication_reminder")},
            "name": "Medication Reminder",
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


class MedicationStatsSensor(SensorEntity):
    """Statistics sensor with daily/weekly/monthly/yearly taken/skipped/missed counts."""

    _attr_icon = "mdi:table"

    def __init__(self, hass: HomeAssistant, name: str, times: list[str], history: HistoryManager, source_entity_id: Optional[str], slug: str):
        self.hass = hass
        self._name = name
        self._times = times
        self._history = history
        self._source_entity_id = source_entity_id
        self._slug = slug
        self._state: Optional[int] = None  # percent last 30d
        self._attr_name = f"{name} Stats"
        self._attr_unique_id = f"med_{slug}_stats"
        self.entity_id = async_generate_entity_id("sensor.{}", f"medication_{slug}_stats", hass=hass)
        self._unsub_dispatcher = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "medication_reminder")},
            "name": "Medication Reminder",
        }

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
        # 30-day adherence percent
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
