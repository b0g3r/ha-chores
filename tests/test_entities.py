"""Tests that chore entities are created and reflect store state."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry_with_one_chore(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            "chores": {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_status_sensor_reflects_not_due(hass):
    await _setup_entry_with_one_chore(hass)
    state = hass.states.get("sensor.dishwasher_maintenance_status")
    assert state is not None
    assert state.state == "ok"


async def test_due_binary_sensor_reflects_not_due(hass):
    await _setup_entry_with_one_chore(hass)
    state = hass.states.get("binary_sensor.dishwasher_maintenance_due")
    assert state is not None
    assert state.state == "off"


async def test_mark_complete_button_exists(hass):
    await _setup_entry_with_one_chore(hass)
    assert hass.states.get("button.dishwasher_maintenance_mark_complete") is not None
