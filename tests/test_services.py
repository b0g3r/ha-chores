"""Tests for the chores.log_cycle and chores.mark_complete services."""
import pytest
from homeassistant.exceptions import ServiceValidationError
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


async def test_button_press_completes_chore_end_to_end(hass):
    """Task 4's button entity calls chores.mark_complete by string name; verify the
    literal actually matches services.py's registration, not just that it compiles."""
    await _setup_entry_with_one_chore(hass)
    for _ in range(30):
        await hass.services.async_call(
            DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True
        )
    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "due"

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.dishwasher_maintenance_mark_complete"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "ok"
    assert hass.states.get("binary_sensor.dishwasher_maintenance_due").state == "off"


async def test_mark_complete_rejects_unknown_chore_id(hass):
    await _setup_entry_with_one_chore(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "mark_complete", {"chore_id": "does-not-exist"}, blocking=True
        )


async def test_log_cycle_rejects_interval_mode_chore_with_service_validation_error(
    hass,
):
    """chore.py's Chore.log_cycle raises a bare ValueError for non-cycle-count chores;
    the service handler must translate that into ServiceValidationError like it already
    does for an unknown chore_id, not let the raw ValueError escape."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            "chores": {
                "c2": {
                    "name": "Water plants",
                    "mode": "interval_days",
                    "interval_days": 7,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "log_cycle", {"chore_id": "c2"}, blocking=True
        )
