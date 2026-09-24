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

    # Patch at the class level: homeassistant's ServiceRegistry uses __slots__, so
    # instances have no __dict__ and patch.object(hass.services, ...) fails with
    # "attribute is read-only".
    with patch.object(type(hass.services), "async_call", return_value=None):
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


# ---------------------------------------------------------------------------
# Nag scheduling
# ---------------------------------------------------------------------------


async def test_nag_stops_after_nag_max(hass, history_mgr):
    """Regression test for an infinite-nag bug.

    _async_send_reminder() used to unconditionally call _start_nags() at its end,
    including when it was invoked from the nag callback itself to resend the
    reminder. That reset _nag_remaining back to nag_max on every single nag
    firing, so nag_max was never actually enforced and reminders nagged forever
    regardless of the configured limit. Fixed by splitting the plain notification
    send (_send_notification, used by nag resends) from the initial
    send-and-start-nagging path (_async_send_reminder, used only for the first
    fire of a slot/snooze-expiry).
    """
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from custom_components.medication_reminder.sensor import MedicationSensor

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["history"] = history_mgr
    hass.data[DOMAIN].setdefault("entities", {})

    nag_max = 2
    sensor = MedicationSensor(
        hass=hass,
        name="Aspirin",
        dose="81mg",
        times=["08:00"],
        snooze_minutes=5,
        notify_services=[],
        nag_interval=1,
        nag_max=nag_max,
        refill_total=0,
        refill_threshold=0,
        units_per_intake=1,
        entry_id="test_entry_nag",
    )
    sensor.entity_id = "sensor.medication_aspirin_nag"
    sensor.async_write_ha_state = MagicMock()
    hass.data[DOMAIN]["entities"][sensor.entity_id] = sensor

    sent = {"n": 0}
    original_send = sensor._send_notification

    async def _counting_send():
        sent["n"] += 1
        await original_send()

    sensor._send_notification = _counting_send

    try:
        await sensor._async_send_reminder()  # initial fire, starts the nag cycle
        await hass.async_block_till_done()
        assert sent["n"] == 1

        # Advance time well past nag_max * nag_interval. With the bug, each nag
        # resend restarted the cycle, so nags never stopped and this loop would
        # keep sending indefinitely.
        now = dt_util.utcnow()
        for _ in range(6):
            now += timedelta(minutes=2)
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()

        # 1 initial send + at most nag_max resends.
        assert sent["n"] <= 1 + nag_max
        # The nag cycle must have stopped on its own.
        assert sensor._nag_unsub is None
        assert sensor._nag_remaining == 0
    finally:
        await sensor.async_will_remove_from_hass()
