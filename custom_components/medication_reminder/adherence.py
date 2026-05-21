"""Adherence and statistics sensor entities for Medication Reminder."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity import async_generate_entity_id, DeviceInfo

from .const import DOMAIN, SIGNAL_HISTORY_UPDATED
from .helpers import slugify
from .history import HistoryManager

_LOGGER = logging.getLogger(__name__)


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
