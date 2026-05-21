"""Shared fixtures for medication_reminder tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

DOMAIN = "medication_reminder"


@pytest.fixture
def mock_store():
    """Patch Store so HistoryManager never touches disk."""
    with patch("custom_components.medication_reminder.history.Store") as mock_cls:
        inst = AsyncMock()
        inst.async_load.return_value = None
        inst.async_save.return_value = None
        mock_cls.return_value = inst
        yield inst


@pytest.fixture
async def history_mgr(hass, mock_store):
    """Loaded HistoryManager backed by a mock store."""
    from custom_components.medication_reminder.history import HistoryManager

    mgr = HistoryManager(hass)
    await mgr.async_load()
    return mgr


@pytest.fixture
async def med_sensor(hass, history_mgr):
    """
    MedicationSensor wired into hass with a mock-backed HistoryManager.

    Startup scheduling is bypassed so tests focus on state/refill logic.
    """
    from custom_components.medication_reminder.sensor import MedicationSensor

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["history"] = history_mgr
    hass.data[DOMAIN].setdefault("entities", {})

    sensor = MedicationSensor(
        hass=hass,
        name="Aspirin",
        dose="81mg",
        times=["08:00"],
        snooze_minutes=5,
        notify_services=[],
        nag_interval=0,
        nag_max=0,
        refill_total=30,
        refill_threshold=5,
        units_per_intake=1,
        entry_id="test_entry_aspirin",
    )
    sensor.entity_id = "sensor.medication_aspirin"
    # Prevent SensorEntity from trying to push to the state machine
    sensor.async_write_ha_state = MagicMock()

    # Register so service-level lookups work
    hass.data[DOMAIN]["entities"][sensor.entity_id] = sensor

    # Prime refill so decrement tests have data
    await history_mgr.set_refill(
        sensor.entity_id,
        remaining=30,
        threshold=5,
        units_per_intake=1,
    )

    return sensor
