"""Tests that chore entities are created and reflect store state."""
from .conftest import setup_entry_with_one_chore


async def test_status_sensor_reflects_not_due(hass):
    await setup_entry_with_one_chore(hass)
    state = hass.states.get("sensor.dishwasher_maintenance_status")
    assert state is not None
    assert state.state == "ok"


async def test_due_binary_sensor_reflects_not_due(hass):
    await setup_entry_with_one_chore(hass)
    state = hass.states.get("binary_sensor.dishwasher_maintenance_due")
    assert state is not None
    assert state.state == "off"


async def test_mark_complete_button_exists(hass):
    await setup_entry_with_one_chore(hass)
    assert hass.states.get("button.dishwasher_maintenance_mark_complete") is not None
