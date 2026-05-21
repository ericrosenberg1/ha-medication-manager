# Sentry — Medication Reminder (Home Assistant integration)

Project: `rosenberg-digital/ha-medication-manager` · platform `python`

## Design: opt-in only

This integration is distributed publicly via HACS, so it does NOT
automatically send telemetry. `custom_components/medication_reminder/sentry.py`
only initialises Sentry if the `MEDREM_SENTRY_DSN` env var is set on the
host Home Assistant instance AND `sentry-sdk` is importable.

End users running HACS get zero telemetry unless they explicitly opt in.

## Enabling on Eric's own HA instance

Set in HA's environment (e.g. `/etc/systemd/system/home-assistant.service.d/override.conf`
or HACS supervisor env):

```ini
[Service]
Environment="MEDREM_SENTRY_DSN=https://ab97111510fb28c0a08460dac399581b@o4507525754060800.ingest.us.sentry.io/4511429590843392"
```

And `pip install sentry-sdk` inside the HA Python env.

Then restart HA. Errors will start flowing to the dashboard.

## In-code reporting

```python
from .sentry import capture_exception

try:
    risky_thing()
except Exception as exc:
    capture_exception(exc, medication_id=med.id)
    raise
```
