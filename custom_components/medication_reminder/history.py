"""Adherence history manager and helpers."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List

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
        self._events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._refill: Dict[str, Dict[str, Any]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        events = data.get("events", {})
        refill = data.get("refill", {})
        # Basic validation
        for eid, lst in events.items():
            if isinstance(lst, list):
                self._events[eid] = [e for e in lst if isinstance(e, dict) and "status" in e and "timestamp" in e]
        if isinstance(refill, dict):
            out: Dict[str, Dict[str, Any]] = {}
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
        await self._store.async_save({"events": self._events, "refill": self._refill})

    async def record(self, entity_id: str, status: str, timestamp_iso: str) -> None:
        lst = self._events[entity_id]
        lst.append({"status": status, "timestamp": timestamp_iso})
        # prune to last 60 days or last 500 events
        cutoff = dt_util.now() - timedelta(days=60)
        pruned: List[Dict[str, Any]] = []
        for e in lst[-500:]:
            ts = dt_util.parse_datetime(e.get("timestamp"))
            if ts is None:
                continue
            if ts >= cutoff:
                pruned.append(e)
        self._events[entity_id] = pruned
        await self._async_save()
        async_dispatcher_send(self.hass, SIGNAL_HISTORY_UPDATED, entity_id)

    def recent(self, entity_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return list(self._events.get(entity_id, []))[-limit:]

    def counts_since(self, entity_id: str, since) -> Dict[str, int]:
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

    def counts_between(self, entity_id: str, start, end) -> Dict[str, int]:
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

    def get_refill(self, entity_id: str) -> Dict[str, Any] | None:
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

    async def decrement_refill(self, entity_id: str, amount: int) -> Dict[str, Any] | None:
        info = self._refill.get(entity_id)
        if not info:
            return None
        info = dict(info)
        info["remaining"] = max(0, int(info.get("remaining", 0)) - int(amount))
        self._refill[entity_id] = info
        await self._async_save()
        return info
