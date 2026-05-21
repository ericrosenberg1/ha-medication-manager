"""Optional Sentry error reporting for medication_reminder.

This module does NOT bundle the Sentry SDK. The integration is distributed
publicly via HACS, and sending data to a third-party Sentry org without
explicit user consent would be inappropriate.

Behaviour:
  - If the environment variable ``MEDREM_SENTRY_DSN`` is set on the host
    Home Assistant instance, AND the ``sentry-sdk`` package is importable,
    Sentry is initialised on the integration's first load.
  - Otherwise, this module is a no-op.

End users do not opt in to anything they don't explicitly configure.
For Eric Rosenberg's own HA instance, setting

    MEDREM_SENTRY_DSN=https://ab97111510fb28c0a08460dac399581b@o4507525754060800.ingest.us.sentry.io/4511429590843392

in HA's environment (``/etc/systemd/system/home-assistant.service.d/override.conf``
or HACS supervised env) is enough to start receiving events.
"""

from __future__ import annotations

import logging
import os
from typing import Final

_LOGGER: Final = logging.getLogger(__name__)

_INITIALIZED: bool = False


def maybe_init_sentry() -> None:
    """Initialise Sentry if MEDREM_SENTRY_DSN is set and sentry-sdk is installed."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    dsn = os.getenv("MEDREM_SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        _LOGGER.debug(
            "MEDREM_SENTRY_DSN is set but sentry-sdk is not installed; "
            "run `pip install sentry-sdk` in the HA env to enable reporting"
        )
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("MEDREM_SENTRY_ENVIRONMENT", "production"),
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=float(os.getenv("MEDREM_SENTRY_TRACES_SAMPLE_RATE", "0.2")),
        send_default_pii=False,
        release=os.getenv("MEDREM_SENTRY_RELEASE"),
    )
    sentry_sdk.set_tag("integration", "medication_reminder")
    _INITIALIZED = True
    _LOGGER.info("Sentry initialised for medication_reminder integration")


def capture_exception(exc: BaseException, **extra) -> None:
    """Safely report an exception if Sentry is configured. No-op otherwise."""
    try:
        import sentry_sdk
        if extra:
            with sentry_sdk.push_scope() as scope:
                for k, v in extra.items():
                    scope.set_extra(k, v)
                sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_exception(exc)
    except ImportError:
        pass
