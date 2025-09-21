import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.medication_reminder.const import (
    DOMAIN,
    ATTR_NAME,
    ATTR_DOSE,
    ATTR_TIMES,
)


async def _setup_entry(hass):
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
    return entry


@pytest.mark.asyncio
async def test_entities_and_services(hass):
    await _setup_entry(hass)

    med = hass.states.get("sensor.medication_aspirin")
    assert med is not None
    assert med.attributes.get("dose") == "100mg"
    assert ["08:00", "20:00"] == med.attributes.get("times")

    hist = hass.states.get("sensor.medication_aspirin_adherence")
    assert hist is not None

    # Mark taken
    await hass.services.async_call(
        DOMAIN,
        "mark_taken",
        {"entity_id": "sensor.medication_aspirin"},
        blocking=True,
    )
    med = hass.states.get("sensor.medication_aspirin")
    assert med.state == "Taken"

    hist = hass.states.get("sensor.medication_aspirin_adherence")
    attrs = hist.attributes
    assert attrs.get("taken_7d", 0) >= 1
    assert isinstance(attrs.get("recent_events"), list)
    assert len(attrs.get("recent_events")) >= 1

    # Mark skipped
    await hass.services.async_call(
        DOMAIN,
        "mark_skipped",
        {"entity_id": "sensor.medication_aspirin"},
        blocking=True,
    )
    med = hass.states.get("sensor.medication_aspirin")
    assert med.state == "Skipped"

    # Snooze
    await hass.services.async_call(
        DOMAIN,
        "mark_snoozed",
        {"entity_id": "sensor.medication_aspirin", "minutes": 1},
        blocking=True,
    )
    med = hass.states.get("sensor.medication_aspirin")
    assert med.state == "Snoozed"


@pytest.mark.asyncio
async def test_mobile_action_event(hass):
    await _setup_entry(hass)

    # Fire a mobile action event
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {
            "action": "MED_TAKEN",
            "action_data": {"entity_id": "sensor.medication_aspirin"},
        },
    )
    await hass.async_block_till_done()

    med = hass.states.get("sensor.medication_aspirin")
    assert med.state == "Taken"
