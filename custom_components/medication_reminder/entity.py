"""Entity definitions for Medication Reminder."""
from homeassistant.components.sensor import SensorEntity

class MedicationEntity(SensorEntity):
    """Represents a medication as a sensor entity."""

    def __init__(self, med):
        self._attr_name = med["name"]
        self._attr_unique_id = f"med_{med['name'].lower().replace(' ', '_')}"
        self._attr_state = "Pending"
        self._attr_extra_state_attributes = {
            "dose": med.get("dose"),
            "times": med.get("times"),
            "last_action": med.get("last_action"),
        }

    @property
    def state(self):
        return self._attr_state
