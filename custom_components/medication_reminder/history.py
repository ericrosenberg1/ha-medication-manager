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

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        events = data.get("events", {})
        # Basic validation
        for eid, lst in events.items():
            if isinstance(lst, list):
                self._events[eid] = [e for e in lst if isinstance(e, dict) and "status" in e and "timestamp" in e]

    async def _async_save(self) -> None:
        await self._store.async_save({"events": self._events})

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
