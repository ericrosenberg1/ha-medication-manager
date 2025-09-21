"""Constants for Medication Reminder."""

# Integration domain must match the folder name under custom_components
DOMAIN = "medication_reminder"

# Storage constants (kept for potential future use)
STORAGE_KEY = "medication_reminder"
STORAGE_VERSION = 1

# Defaults
DEFAULT_SNOOZE_MINUTES = 5
MIN_SNOOZE_MINUTES = 1
MAX_SNOOZE_MINUTES = 1440

# Common attribute keys
ATTR_NAME = "name"
ATTR_DOSE = "dose"
ATTR_TIMES = "times"
ATTR_LAST_ACTION = "last_action"

# States
STATE_PENDING = "Pending"
STATE_TAKEN = "Taken"
STATE_SKIPPED = "Skipped"
STATE_SNOOZED = "Snoozed"

# History persistence
HISTORY_STORE_KEY = f"{DOMAIN}_history"
HISTORY_STORE_VERSION = 1
SIGNAL_HISTORY_UPDATED = f"{DOMAIN}_history_updated"
