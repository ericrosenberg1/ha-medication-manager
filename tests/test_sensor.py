"""Integration tests for MedicationSensor (sensor.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.medication_reminder.const import (
    DOMAIN,
    EVENT_STATE_CHANGED,
    STATE_PENDING,
    STATE_SKIPPED,
    STATE_SNOOZED,
    STATE_TAKEN,
)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


async def test_initial_state_is_pending(med_sensor):
    assert med_sensor._state == STATE_PENDING


# ---------------------------------------------------------------------------
# async_mark() — state transitions
# ---------------------------------------------------------------------------


async def test_mark_taken_transitions_state(med_sensor):
    await med_sensor.async_mark(STATE_TAKEN)
    assert med_sensor._state == STATE_TAKEN


async def test_mark_skipped_transitions_state(med_sensor):
    await med_sensor.async_mark(STATE_SKIPPED)
    assert med_sensor._state == STATE_SKIPPED


async def test_mark_pending_resets_from_taken(med_sensor):
    await med_sensor.async_mark(STATE_TAKEN)
    await med_sensor.async_mark(STATE_PENDING)
    assert med_sensor._state == STATE_PENDING


async def test_mark_updates_last_action(med_sensor):
    await med_sensor.async_mark(STATE_TAKEN)
    assert med_sensor._last_action is not None
    assert med_sensor._last_action.status == STATE_TAKEN


async def test_mark_records_event_to_history(med_sensor, history_mgr):
    await med_sensor.async_mark(STATE_TAKEN)
    events = history_mgr._events.get(med_sensor.entity_id, [])
    assert any(e["status"] == STATE_TAKEN for e in events)


async def test_mark_fires_ha_event(med_sensor, hass):
    fired = []
    hass.bus.async_listen(EVENT_STATE_CHANGED, lambda e: fired.append(e))

    await med_sensor.async_mark(STATE_TAKEN)
    await hass.async_block_till_done()

    assert len(fired) == 1
    assert fired[0].data["new_state"] == STATE_TAKEN
    assert fired[0].data["old_state"] == STATE_PENDING
    assert fired[0].data["entity_id"] == med_sensor.entity_id


async def test_mark_same_state_does_not_fire_event(med_sensor, hass):
    """No event when state doesn't actually change."""
    await med_sensor.async_mark(STATE_PENDING)  # stays Pending
    fired = []
    hass.bus.async_listen(EVENT_STATE_CHANGED, lambda e: fired.append(e))
    await med_sensor.async_mark(STATE_PENDING)
    await hass.async_block_till_done()

    assert fired == []


# ---------------------------------------------------------------------------
# async_snooze() — snooze timer
# ---------------------------------------------------------------------------


async def test_snooze_sets_snoozed_state(med_sensor):
    await med_sensor.async_snooze(minutes=10)
    assert med_sensor._state == STATE_SNOOZED


async def test_snooze_records_to_history(med_sensor, history_mgr):
    await med_sensor.async_snooze(minutes=5)
    events = history_mgr._events.get(med_sensor.entity_id, [])
    assert any(e["status"] == "Snoozed" for e in events)


async def test_snooze_persists_until_timestamp(med_sensor, history_mgr):
    before = dt_util.now()
    await med_sensor.async_snooze(minutes=5)
    snooze_iso = history_mgr.get_snooze_until(med_sensor.entity_id)

    assert snooze_iso is not None
    snooze_time = dt_util.parse_datetime(snooze_iso)
    # Should be ~5 minutes ahead
    assert snooze_time > before


async def test_mark_taken_after_snooze_clears_snooze(med_sensor, history_mgr):
    await med_sensor.async_snooze(minutes=5)
    assert history_mgr.get_snooze_until(med_sensor.entity_id) is not None

    await med_sensor.async_mark(STATE_TAKEN)
    assert history_mgr.get_snooze_until(med_sensor.entity_id) is None


# ---------------------------------------------------------------------------
# Midnight reset
# ---------------------------------------------------------------------------


async def test_midnight_reset_returns_to_pending(med_sensor):
    await med_sensor.async_mark(STATE_TAKEN)
    assert med_sensor._state == STATE_TAKEN

    with patch.object(med_sensor, "_schedule_midnight_reset"):
        await med_sensor._async_midnight_reset()

    assert med_sensor._state == STATE_PENDING


async def test_midnight_reset_clears_last_action(med_sensor):
    await med_sensor.async_mark(STATE_TAKEN)
    assert med_sensor._last_action is not None

    with patch.object(med_sensor, "_schedule_midnight_reset"):
        await med_sensor._async_midnight_reset()

    assert med_sensor._last_action is None


async def test_midnight_reset_fires_ha_event(med_sensor, hass):
    await med_sensor.async_mark(STATE_TAKEN)

    fired = []
    hass.bus.async_listen(EVENT_STATE_CHANGED, lambda e: fired.append(e))

    with patch.object(med_sensor, "_schedule_midnight_reset"):
        await med_sensor._async_midnight_reset()

    await hass.async_block_till_done()
    assert any(e.data["new_state"] == STATE_PENDING for e in fired)


async def test_midnight_reset_no_event_when_already_pending(med_sensor, hass):
    # State is already Pending; reset should be silent
    fired = []
    hass.bus.async_listen(EVENT_STATE_CHANGED, lambda e: fired.append(e))

    with patch.object(med_sensor, "_schedule_midnight_reset"):
        await med_sensor._async_midnight_reset()

    await hass.async_block_till_done()
    assert fired == []


# ---------------------------------------------------------------------------
# Refill decrement on Taken
# ---------------------------------------------------------------------------


async def test_refill_decremented_on_mark_taken(med_sensor, history_mgr):
    eid = med_sensor.entity_id
    await history_mgr.set_refill(eid, remaining=10, threshold=2, units_per_intake=1)

    await med_sensor.async_mark(STATE_TAKEN)

    info = history_mgr.get_refill(eid)
    assert info["remaining"] == 9


async def test_refill_decremented_by_units_per_intake(med_sensor, history_mgr):
    eid = med_sensor.entity_id
    med_sensor._units_per_intake = 3
    await history_mgr.set_refill(eid, remaining=10, threshold=2, units_per_intake=3)

    await med_sensor.async_mark(STATE_TAKEN)

    info = history_mgr.get_refill(eid)
    assert info["remaining"] == 7


async def test_refill_alert_set_when_below_threshold(med_sensor, history_mgr, hass):
    """
    When remaining drops to threshold after Taken, alerted flag is set.
    persistent_notification is a core HA service so we mock async_call to
    avoid needing the full HA component stack in the test environment.
    """
    eid = med_sensor.entity_id
    # remaining will become 5 == threshold → alert fires
    await history_mgr.set_refill(eid, remaining=6, threshold=5, units_per_intake=1)

    with patch.object(hass.services, "async_call", return_value=None):
        await med_sensor.async_mark(STATE_TAKEN)
        await hass.async_block_till_done()

    info = history_mgr.get_refill(eid)
    assert info["remaining"] == 5
    assert info["alerted"] is True


async def test_refill_skipped_does_not_decrement(med_sensor, history_mgr):
    eid = med_sensor.entity_id
    await history_mgr.set_refill(eid, remaining=10, threshold=2, units_per_intake=1)

    await med_sensor.async_mark(STATE_SKIPPED)

    info = history_mgr.get_refill(eid)
    assert info["remaining"] == 10
