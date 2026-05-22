# ha-medication-manager — Claude Code Instructions

## Tech stack
- Home Assistant HACS custom integration (Python 3.11+)
- pytest-homeassistant-custom-component for testing

## Auto-fix guidelines
- **Test command:** `python -m pytest tests/ -v --tb=short`
- Only modify the Python file shown in the stack trace
- Do not modify `manifest.json` version — version bumps are separate PRs
- All HA service/state calls must be async (`await hass.services.async_call(...)`)
- Storage via `HistoryManager` from `history.py` — not raw `hass.data` writes
- Always use `hass.data[DOMAIN].get(key)` pattern (not bare `[]`) to avoid KeyError on unload

## File map
- `custom_components/medication_reminder/sensor.py` — main sensor, state machine, async_mark/snooze
- `custom_components/medication_reminder/history.py` — persistence (HistoryManager, debounced save)
- `custom_components/medication_reminder/services.py` — MedicationServices class (7 service handlers)
- `custom_components/medication_reminder/adherence.py` — adherence/stats sensors
- `custom_components/medication_reminder/const.py` — all constants (DOMAIN, states, URLs)
- `tests/` — pytest suite (test_sensor.py, test_history.py, conftest.py)