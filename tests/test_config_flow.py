import pytest

from homeassistant import data_entry_flow

from custom_components.medication_reminder.const import (
    DOMAIN,
    ATTR_NAME,
    ATTR_DOSE,
    ATTR_TIMES,
)


@pytest.mark.asyncio
async def test_config_flow_success(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    user_input = {ATTR_NAME: "Aspirin", ATTR_DOSE: "100mg", ATTR_TIMES: "8:00, 20:00"}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    data = result2["data"]
    assert data[ATTR_NAME] == "Aspirin"
    assert data[ATTR_DOSE] == "100mg"
    assert data[ATTR_TIMES] == ["08:00", "20:00"]


@pytest.mark.asyncio
async def test_config_flow_invalid_times(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    user_input = {ATTR_NAME: "Aspirin", ATTR_DOSE: "100mg", ATTR_TIMES: "25:00"}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"]["base"] == "invalid_times"
