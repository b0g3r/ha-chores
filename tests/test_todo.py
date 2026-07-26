"""Tests for the active-chores to-do list."""
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


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
                    "nfc_enabled": False,
                    "notification_enabled": True,
                    "notify_enabled": True,
                    "notify_time": "08:00:00",
                },
                "c2": {
                    "name": "Water plants",
                    "mode": "interval_days",
                    "interval_days": 7,
                    "nfc_enabled": False,
                    "notification_enabled": True,
                    "notify_enabled": True,
                    "notify_time": "08:00:00",
                },
                "c3_not_due": {
                    "name": "Not due yet",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "nfc_enabled": False,
                    "notification_enabled": True,
                    "notify_enabled": True,
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
    # c3_not_due stays at count=0 (threshold 30) -- genuinely not due

    result = await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": "todo.chores"},
        blocking=True,
        return_response=True,
    )
    uids = {item["uid"] for item in result["todo.chores"]["items"]}
    assert uids == {"c1", "c2"}
    # c3_not_due (never completed, count never reached its threshold) is excluded

    state = hass.states.get("todo.chores")
    assert state is not None


async def test_completing_a_chore_removes_it_from_the_list(hass):
    entry = await _setup_entry_with_two_chores(hass)
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30

    await hass.services.async_call(
        DOMAIN, "mark_complete", {"chore_id": "c1"}, blocking=True
    )
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": "todo.chores"},
        blocking=True,
        return_response=True,
    )
    uids = {item["uid"] for item in result["todo.chores"]["items"]}
    assert "c1" not in uids  # completed, no longer due
    assert uids == {"c2"}  # c2 still due, c3_not_due never was

    state = hass.states.get("todo.chores")
    assert state is not None
    assert state.state == "1"
