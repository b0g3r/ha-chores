"""Tests for the hub config flow and options flow."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.config_flow import ChoresOptionsFlow
from custom_components.chores.const import (
    CONF_CHORES,
    CONF_PERSON_NOTIFY_MAP,
    DOMAIN,
)


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
            "notify_time": "08:00:00",
        },
    )
    assert result["type"] == "create_entry"
    chores = entry.options[CONF_CHORES]
    assert len(chores) == 1
    (chore_config,) = chores.values()
    assert chore_config["name"] == "Dishwasher maintenance"


async def test_remove_chore_deletes_selected_chore_keeps_others(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            CONF_CHORES: {
                "id1": {"name": "Vacuum"},
                "id2": {"name": "Dishwasher maintenance"},
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove_chore"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"chore_id": "id1"}
    )

    assert result["type"] == "create_entry"
    remaining = entry.options[CONF_CHORES]
    assert list(remaining) == ["id2"]


async def test_remove_chore_aborts_when_no_chores(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chores & Maintenance", data={}, options={}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove_chore"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_chores"


async def test_notify_mapping_sets_mapping_and_reads_person_entities(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chores & Maintenance", data={}, options={}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    hass.states.async_set("person.alice", "home")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "notify_mapping"}
    )
    assert result["type"] == "form"
    field_names = [key.schema for key in result["data_schema"].schema]
    assert "person.alice" in field_names

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"person.alice": "notify.mobile_app_alice"}
    )

    assert result["type"] == "create_entry"
    assert entry.options[CONF_PERSON_NOTIFY_MAP] == {
        "person.alice": "notify.mobile_app_alice"
    }


def _options_flow(hass, entry):
    flow = ChoresOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    return flow


async def test_add_chore_requires_interval_days_for_interval_mode(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chores & Maintenance", data={}, options={}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await _options_flow(hass, entry).async_step_add_chore(
        {
            "name": "Vacuum",
            "mode": "interval_days",
            "interval_days": 0,
            "cycle_threshold": 30,
            "completion_method": "notification_action",
            "notify_time": "08:00:00",
        }
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "interval_days_required"


async def test_add_chore_requires_cycle_threshold_for_cycle_count_mode(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chores & Maintenance", data={}, options={}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await _options_flow(hass, entry).async_step_add_chore(
        {
            "name": "Vacuum",
            "mode": "cycle_count",
            "interval_days": 7,
            "cycle_threshold": 0,
            "completion_method": "notification_action",
            "notify_time": "08:00:00",
        }
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cycle_threshold_required"


async def test_add_chore_requires_nfc_tag_when_completion_method_needs_it(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chores & Maintenance", data={}, options={}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await _options_flow(hass, entry).async_step_add_chore(
        {
            "name": "Vacuum",
            "mode": "interval_days",
            "interval_days": 7,
            "cycle_threshold": 30,
            "completion_method": "nfc_tag",
            "notify_time": "08:00:00",
        }
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "nfc_tag_required"
