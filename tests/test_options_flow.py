import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.medication_reminder.const import (
    DOMAIN,
    ATTR_NAME,
    ATTR_DOSE,
    ATTR_TIMES,
)


@pytest.mark.asyncio
async def test_options_flow_updates_entity(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            ATTR_NAME: "Aspirin",
            ATTR_DOSE: "100mg",
            ATTR_TIMES: ["08:00", "20:00"],
        },
        options={},
        title="Aspirin",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Open options
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"

    # Submit new values
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_DOSE: "200mg",
            ATTR_TIMES: "09:00, 21:00",
            "snooze_minutes": 7,
            "notify_services": "notify.test",
        },
    )
    assert result2["type"] == "create_entry"

    # Entity should reflect updates
    state = hass.states.get("sensor.medication_aspirin")
    assert state.attributes.get("dose") == "200mg"
    assert ["09:00", "21:00"] == state.attributes.get("times")
