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

# API endpoints
RXTERMS_API_URL = "https://clinicaltables.nlm.nih.gov/api/rxterms/v3/search"
OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"

# Cache
INTERACTION_CACHE_TTL = 86400  # 24 hours in seconds

# Events
EVENT_INTERACTION_WARNING = f"{DOMAIN}_interaction_warning"

# Drug interaction attributes
ATTR_RXCUI = "rxcui"
ATTR_DRUG_INFO = "drug_info"
