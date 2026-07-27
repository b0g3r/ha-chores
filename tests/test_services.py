"""Tests for the chores.log_cycle and chores.mark_complete services."""
from datetime import date, timedelta

import pytest
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN

from .conftest import setup_entry_with_one_chore


async def test_log_cycle_increments_count_and_updates_sensor(hass):
    await setup_entry_with_one_chore(hass)

    for _ in range(30):
        await hass.services.async_call(
            DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True
        )

    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "due"
    assert hass.states.get("binary_sensor.dishwasher_maintenance_due").state == "on"


async def test_mark_complete_resets_and_updates_sensor(hass):
    await setup_entry_with_one_chore(hass)
    for _ in range(30):
        await hass.services.async_call(
            DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True
        )

    await hass.services.async_call(
        DOMAIN, "mark_complete", {"chore_id": "c1"}, blocking=True
    )

    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "ok"
    assert hass.states.get("binary_sensor.dishwasher_maintenance_due").state == "off"


async def test_mark_complete_accepts_backdated_completed_on(hass):
    """Migrating an existing chore needs to record it as already partway through its
    interval (e.g. "last done 10 days ago"), not just "done today" -- mark_complete
    must accept an explicit completed_on date and persist it verbatim."""
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
                    "nfc_enabled": False,
                    "notification_enabled": True,
                    "notify_enabled": True,
                    "notify_time": "08:00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    backdated = date.today() - timedelta(days=3)
    await hass.services.async_call(
        DOMAIN,
        "mark_complete",
        {"chore_id": "c2", "completed_on": backdated.isoformat()},
        blocking=True,
    )

    store = hass.data[DOMAIN][entry.entry_id]
    assert store.chores["c2"].last_completed == backdated
    assert store.chores["c2"].is_due(date.today()) is False


async def test_button_press_completes_chore_end_to_end(hass):
    """Task 4's button entity calls chores.mark_complete by string name; verify the
    literal actually matches services.py's registration, not just that it compiles."""
    await setup_entry_with_one_chore(hass)
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
    await setup_entry_with_one_chore(hass)

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
                    "nfc_enabled": False,
                    "notification_enabled": True,
                    "notify_enabled": True,
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
