"""Config flow for Medication Reminder integration."""
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class MedicationReminderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Medication Reminder", data=user_input)

        schema = vol.Schema({
            vol.Required("name"): str,
            vol.Optional("dose", default=""): str,
            vol.Required("times"): str,  # Comma-separated: e.g., "08:00,20:00"
        })
        return self.async_show_form(step_id="user", data_schema=schema)
