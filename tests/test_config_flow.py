"""Tests for the hub config flow and options flow."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import CONF_CHORES, DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def test_user_flow_creates_single_hub_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    assert result["title"] == "Chores & Maintenance"


async def test_user_flow_aborts_if_hub_already_exists(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Chores & Maintenance", data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_add_chore_via_options_flow(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chores & Maintenance", data={}, options={}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_chore"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Dishwasher maintenance",
            "mode": "cycle_count",
            "interval_days": 7,
            "cycle_threshold": 30,
            "completion_method": "notification_action",
            "nfc_tag_entity_id": "",
            "notify_time": "08:00:00",
        },
    )
    assert result["type"] == "create_entry"
    chores = entry.options[CONF_CHORES]
    assert len(chores) == 1
    (chore_config,) = chores.values()
    assert chore_config["name"] == "Dishwasher maintenance"
