"""Adherence history manager and helpers."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    HISTORY_STORE_KEY,
    HISTORY_STORE_VERSION,
    SIGNAL_HISTORY_UPDATED,
)


class HistoryManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, HISTORY_STORE_VERSION, HISTORY_STORE_KEY)
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._refill: dict[str, dict[str, Any]] = {}
        # Tracks the last date each time slot fired per entity (for restart recovery)
        # Format: {entity_id: {"08:00": "2026-04-04", "20:00": "2026-04-04"}}
        self._last_reminded: dict[str, dict[str, str]] = {}
        # Tracks active snooze expiry per entity (for restart recovery)
        # Format: {entity_id: "2026-04-04T08:15:00+00:00"}
        self._snooze_until: dict[str, str] = {}
        # Tracks last state per entity (for restart recovery)
        # Format: {entity_id: {"state": "Taken", "timestamp": "...", "date": "2026-04-04"}}
        self._last_state: dict[str, dict[str, str]] = {}
        self._pending_save: asyncio.Task | None = None

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        events = data.get("events", {})
        refill = data.get("refill", {})
        # Load persisted reminder/snooze/state data
        self._last_reminded = data.get("last_reminded", {})
        self._snooze_until = data.get("snooze_until", {})
        self._last_state = data.get("last_state", {})
        # Basic validation
        for eid, lst in events.items():
            if isinstance(lst, list):
                self._events[eid] = [e for e in lst if isinstance(e, dict) and "status" in e and "timestamp" in e]
        if isinstance(refill, dict):
            out: dict[str, dict[str, Any]] = {}
            for eid, info in refill.items():
                if not isinstance(info, dict):
                    continue
                remaining = info.get("remaining")
                threshold = info.get("threshold")
                units = info.get("units_per_intake")
                alerted = info.get("alerted", False)
                try:
                    if remaining is None or threshold is None or units is None:
                        continue
                    remaining = int(remaining)
                    threshold = int(threshold)
                    units = int(units)
                    out[eid] = {
                        "remaining": remaining,
                        "threshold": threshold,
                        "units_per_intake": units,
                        "alerted": bool(alerted),
                    }
                except (TypeError, ValueError):
                    continue
            self._refill = out

    async def _async_save(self) -> None:
        """Write current state to the HA store immediately."""
        await self._store.async_save({
            "events": dict(self._events),
            "refill": self._refill,
            "last_reminded": self._last_reminded,
            "snooze_until": self._snooze_until,
            "last_state": self._last_state,
        })

    def _schedule_save(self, delay: float = 30.0) -> None:
        """Schedule a debounced save. Cancels any pending save and schedules a new one."""
        if self._pending_save is not None and not self._pending_save.done():
            self._pending_save.cancel()

        async def _delayed():
            try:
                await asyncio.sleep(delay)
                await self._async_save()
            except asyncio.CancelledError:
                pass

        self._pending_save = self.hass.async_create_task(_delayed())

    async def async_flush(self) -> None:
        """Cancel pending debounced save and write immediately."""
        if self._pending_save is not None and not self._pending_save.done():
            self._pending_save.cancel()
            self._pending_save = None
        await self._async_save()

    async def record(self, entity_id: str, status: str, timestamp_iso: str) -> None:
        lst = self._events[entity_id]
        lst.append({"status": status, "timestamp": timestamp_iso})
        # prune to last 60 days or last 500 events
        cutoff = dt_util.now() - timedelta(days=60)
        pruned: list[dict[str, Any]] = []
        for e in lst[-500:]:
            ts = dt_util.parse_datetime(e.get("timestamp"))
            if ts is None:
                continue
            if ts >= cutoff:
                pruned.append(e)
        self._events[entity_id] = pruned
        self._schedule_save()  # debounced — writes after 30s idle
        async_dispatcher_send(self.hass, SIGNAL_HISTORY_UPDATED, entity_id)

    def recent(self, entity_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return list(self._events.get(entity_id, []))[-limit:]

    def counts_since(self, entity_id: str, since) -> dict[str, int]:
        taken = skipped = snoozed = 0
        for e in self._events.get(entity_id, []):
            ts = dt_util.parse_datetime(e.get("timestamp"))
            if ts is None or ts < since:
                continue
            status = str(e.get("status"))
            if status.lower().startswith("take"):
                taken += 1
            elif status.lower().startswith("skip"):
                skipped += 1
            elif status.lower().startswith("snooz"):
                snoozed += 1
        return {"taken": taken, "skipped": skipped, "snoozed": snoozed}

    def counts_between(self, entity_id: str, start, end) -> dict[str, int]:
        taken = skipped = snoozed = 0
        for e in self._events.get(entity_id, []):
            ts = dt_util.parse_datetime(e.get("timestamp"))
            if ts is None or ts < start or ts > end:
                continue
            status = str(e.get("status"))
            if status.lower().startswith("take"):
                taken += 1
            elif status.lower().startswith("skip"):
                skipped += 1
            elif status.lower().startswith("snooz"):
                snoozed += 1
        return {"taken": taken, "skipped": skipped, "snoozed": snoozed}

    def get_refill(self, entity_id: str) -> dict[str, Any] | None:
        return self._refill.get(entity_id)

    async def set_refill(self, entity_id: str, remaining: int, threshold: int, units_per_intake: int, alerted: bool = False) -> None:
        self._refill[entity_id] = {
            "remaining": int(remaining),
            "threshold": int(threshold),
            "units_per_intake": int(units_per_intake),
            "alerted": bool(alerted),
        }
        await self._async_save()

    async def adjust_refill(self, entity_id: str, *, remaining: int | None = None, threshold: int | None = None, units_per_intake: int | None = None, alerted: bool | None = None) -> None:
        current = self._refill.get(entity_id) or {}
        new = {
            "remaining": int(remaining if remaining is not None else current.get("remaining", 0)),
            "threshold": int(threshold if threshold is not None else current.get("threshold", 0)),
            "units_per_intake": int(units_per_intake if units_per_intake is not None else current.get("units_per_intake", 1)),
            "alerted": bool(alerted if alerted is not None else current.get("alerted", False)),
        }
        self._refill[entity_id] = new
        await self._async_save()

    async def decrement_refill(self, entity_id: str, amount: int) -> dict[str, Any] | None:
        info = self._refill.get(entity_id)
        if not info:
            return None
        info = dict(info)
        info["remaining"] = max(0, int(info.get("remaining", 0)) - int(amount))
        self._refill[entity_id] = info
        await self._async_save()
        return info

    # --- Reminder state persistence (for restart recovery) ---

    async def set_last_reminded(self, entity_id: str, time_slot: str, date_str: str) -> None:
        """Record that a time slot's reminder fired on a given date (YYYY-MM-DD)."""
        slots = self._last_reminded.setdefault(entity_id, {})
        slots[time_slot] = date_str
        await self._async_save()

    def get_last_reminded(self, entity_id: str) -> dict[str, str]:
        """Return {time_slot: date_str} for an entity."""
        return dict(self._last_reminded.get(entity_id, {}))

    async def set_snooze_until(self, entity_id: str, until_iso: str | None) -> None:
        """Store or clear the snooze expiry for an entity."""
        if until_iso is None:
            self._snooze_until.pop(entity_id, None)
        else:
            self._snooze_until[entity_id] = until_iso
        await self._async_save()

    def get_snooze_until(self, entity_id: str) -> str | None:
        """Return the ISO snooze expiry or None."""
        return self._snooze_until.get(entity_id)

    async def set_last_state(self, entity_id: str, state: str, timestamp: str, date_str: str) -> None:
        """Persist the last known state for restart recovery."""
        self._last_state[entity_id] = {
            "state": state,
            "timestamp": timestamp,
            "date": date_str,
        }
        await self._async_save()

    def get_last_state(self, entity_id: str) -> dict[str, str] | None:
        """Return persisted state info or None."""
        return self._last_state.get(entity_id)
