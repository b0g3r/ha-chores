"""Tests for the chores.log_cycle and chores.mark_complete services."""
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


async def test_log_cycle_increments_count_and_updates_sensor(hass):
    await _setup_entry_with_one_chore(hass)

    for _ in range(30):
        await hass.services.async_call(
            DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True
        )

    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "due"
    assert hass.states.get("binary_sensor.dishwasher_maintenance_due").state == "on"


async def test_mark_complete_resets_and_updates_sensor(hass):
    await _setup_entry_with_one_chore(hass)
    for _ in range(30):
        await hass.services.async_call(
            DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True
        )

    await hass.services.async_call(
        DOMAIN, "mark_complete", {"chore_id": "c1"}, blocking=True
    )

    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "ok"
    assert hass.states.get("binary_sensor.dishwasher_maintenance_due").state == "off"
