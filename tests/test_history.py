"""Unit tests for HistoryManager (history.py)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

EID = "sensor.medication_test"


# ---------------------------------------------------------------------------
# record() — basic append
# ---------------------------------------------------------------------------


async def test_record_appends_event(history_mgr):
    now_iso = dt_util.now().isoformat()
    await history_mgr.record(EID, "Taken", now_iso)

    events = history_mgr._events[EID]
    assert len(events) == 1
    assert events[0]["status"] == "Taken"
    assert events[0]["timestamp"] == now_iso


async def test_record_multiple_events_ordered(history_mgr):
    now = dt_util.now()
    ts1 = (now - timedelta(minutes=5)).isoformat()
    ts2 = now.isoformat()
    await history_mgr.record(EID, "Taken", ts1)
    await history_mgr.record(EID, "Skipped", ts2)

    events = history_mgr._events[EID]
    assert len(events) == 2
    assert events[0]["status"] == "Taken"
    assert events[1]["status"] == "Skipped"


# ---------------------------------------------------------------------------
# Pruning — 60-day cutoff
# ---------------------------------------------------------------------------


async def test_prune_removes_events_older_than_60_days(history_mgr):
    old_ts = (dt_util.now() - timedelta(days=61)).isoformat()
    recent_ts = dt_util.now().isoformat()

    # Pre-load an old event directly (bypassing record's own pruning)
    history_mgr._events[EID] = [{"status": "Taken", "timestamp": old_ts}]

    # Triggering record() should prune the old event
    await history_mgr.record(EID, "Skipped", recent_ts)

    events = history_mgr._events[EID]
    assert len(events) == 1
    assert events[0]["status"] == "Skipped"


async def test_recent_events_within_60_days_are_kept(history_mgr):
    ts59 = (dt_util.now() - timedelta(days=59)).isoformat()
    ts_now = dt_util.now().isoformat()

    history_mgr._events[EID] = [{"status": "Taken", "timestamp": ts59}]
    await history_mgr.record(EID, "Skipped", ts_now)

    assert len(history_mgr._events[EID]) == 2


# ---------------------------------------------------------------------------
# Pruning — 500-event limit
# ---------------------------------------------------------------------------


async def test_prune_keeps_at_most_500_events(history_mgr):
    recent_ts = dt_util.now().isoformat()
    # Pre-load exactly 500 events
    history_mgr._events[EID] = [
        {"status": "Taken", "timestamp": recent_ts} for _ in range(500)
    ]

    # Adding the 501st should evict the oldest
    await history_mgr.record(EID, "Skipped", recent_ts)

    assert len(history_mgr._events[EID]) == 500


# ---------------------------------------------------------------------------
# counts_since()
# ---------------------------------------------------------------------------


async def test_counts_since_empty_history(history_mgr):
    since = dt_util.now() - timedelta(days=7)
    counts = history_mgr.counts_since(EID, since)
    assert counts == {"taken": 0, "skipped": 0, "snoozed": 0}


async def test_counts_since_classifies_statuses(history_mgr):
    now = dt_util.now()
    recent = now.isoformat()
    outside = (now - timedelta(days=10)).isoformat()  # beyond 7-day window

    history_mgr._events[EID] = [
        {"status": "Taken", "timestamp": recent},
        {"status": "Taken", "timestamp": recent},
        {"status": "Skipped", "timestamp": recent},
        {"status": "Snoozed", "timestamp": recent},
        {"status": "Taken", "timestamp": outside},  # excluded
    ]

    since = now - timedelta(days=7)
    counts = history_mgr.counts_since(EID, since)

    assert counts == {"taken": 2, "skipped": 1, "snoozed": 1}


async def test_counts_since_boundary_inclusive(history_mgr):
    """Events exactly at the 'since' boundary should be included (ts >= since)."""
    since = dt_util.now() - timedelta(days=7)
    history_mgr._events[EID] = [
        {"status": "Taken", "timestamp": since.isoformat()},
    ]

    counts = history_mgr.counts_since(EID, since)
    assert counts["taken"] == 1


# ---------------------------------------------------------------------------
# counts_between()
# ---------------------------------------------------------------------------


async def test_counts_between_inside_window(history_mgr):
    now = dt_util.now()
    inside = (now - timedelta(days=2)).isoformat()
    outside = (now - timedelta(days=10)).isoformat()

    history_mgr._events[EID] = [
        {"status": "Taken", "timestamp": inside},
        {"status": "Skipped", "timestamp": outside},
    ]

    start = now - timedelta(days=7)
    counts = history_mgr.counts_between(EID, start, now)

    assert counts == {"taken": 1, "skipped": 0, "snoozed": 0}


async def test_counts_between_excludes_after_end(history_mgr):
    now = dt_util.now()
    future = (now + timedelta(hours=1)).isoformat()

    history_mgr._events[EID] = [
        {"status": "Taken", "timestamp": future},
    ]

    counts = history_mgr.counts_between(EID, now - timedelta(days=1), now)
    assert counts["taken"] == 0


# ---------------------------------------------------------------------------
# Refill — set / get
# ---------------------------------------------------------------------------


async def test_set_and_get_refill(history_mgr):
    await history_mgr.set_refill(EID, remaining=30, threshold=5, units_per_intake=2)
    info = history_mgr.get_refill(EID)

    assert info["remaining"] == 30
    assert info["threshold"] == 5
    assert info["units_per_intake"] == 2
    assert info["alerted"] is False


async def test_get_refill_none_when_unset(history_mgr):
    assert history_mgr.get_refill("sensor.medication_unregistered") is None


# ---------------------------------------------------------------------------
# Refill — decrement
# ---------------------------------------------------------------------------


async def test_decrement_refill(history_mgr):
    await history_mgr.set_refill(EID, remaining=10, threshold=2, units_per_intake=1)
    updated = await history_mgr.decrement_refill(EID, 3)

    assert updated["remaining"] == 7


async def test_decrement_refill_floors_at_zero(history_mgr):
    await history_mgr.set_refill(EID, remaining=1, threshold=0, units_per_intake=1)
    updated = await history_mgr.decrement_refill(EID, 100)

    assert updated["remaining"] == 0


async def test_decrement_refill_returns_none_when_unset(history_mgr):
    result = await history_mgr.decrement_refill("sensor.medication_nope", 1)
    assert result is None


# ---------------------------------------------------------------------------
# Refill — adjust (partial update)
# ---------------------------------------------------------------------------


async def test_adjust_refill_partial_update(history_mgr):
    await history_mgr.set_refill(EID, remaining=30, threshold=5, units_per_intake=1)
    await history_mgr.adjust_refill(EID, remaining=20)

    info = history_mgr.get_refill(EID)
    assert info["remaining"] == 20
    assert info["threshold"] == 5  # unchanged


async def test_adjust_refill_alerted_flag(history_mgr):
    await history_mgr.set_refill(EID, remaining=30, threshold=5, units_per_intake=1)
    await history_mgr.adjust_refill(EID, alerted=True)

    assert history_mgr.get_refill(EID)["alerted"] is True


async def test_refill_add_pattern(history_mgr):
    """Simulate refill_add service: adjust remaining = old + amount, clear alert."""
    await history_mgr.set_refill(EID, remaining=5, threshold=10, units_per_intake=1, alerted=True)

    old = history_mgr.get_refill(EID)
    await history_mgr.adjust_refill(EID, remaining=old["remaining"] + 30, alerted=False)

    info = history_mgr.get_refill(EID)
    assert info["remaining"] == 35
    assert info["alerted"] is False
