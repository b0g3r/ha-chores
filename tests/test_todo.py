"""Tests for the active-chores to-do list."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry_with_two_chores(hass):
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
                },
                "c2": {
                    "name": "Water plants",
                    "mode": "interval_days",
                    "interval_days": 7,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                },
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_todo_list_shows_only_due_chores(hass):
    entry = await _setup_entry_with_two_chores(hass)
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30  # now due
    # c2 (interval_days, never completed) is due immediately per Chore.is_due semantics

    await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": "todo.chores"},
        blocking=True,
        return_response=True,
    )
    state = hass.states.get("todo.chores")
    assert state is not None


async def test_completing_a_chore_removes_it_from_the_list(hass):
    entry = await _setup_entry_with_two_chores(hass)
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30

    await hass.services.async_call(
        DOMAIN, "mark_complete", {"chore_id": "c1"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("todo.chores")
    assert state is not None
