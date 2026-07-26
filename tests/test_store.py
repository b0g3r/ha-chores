"""Tests for chore runtime state persistence."""
from custom_components.chores.store import ChoreStore

CHORE_CONFIGS = {
    "c1": {"name": "Dishwasher maintenance", "mode": "cycle_count", "cycle_threshold": 30},
}


async def test_store_round_trips_runtime_state(hass):
    store = ChoreStore(hass, "test_entry")
    await store.async_load(CHORE_CONFIGS)
    store.chores["c1"].log_cycle()
    await store.async_save()

    reloaded = ChoreStore(hass, "test_entry")
    await reloaded.async_load(CHORE_CONFIGS)
    assert reloaded.chores["c1"].count == 1


async def test_store_defaults_new_chore_to_zero_state(hass):
    store = ChoreStore(hass, "test_entry_2")
    await store.async_load(CHORE_CONFIGS)
    assert store.chores["c1"].count == 0
    assert store.chores["c1"].last_completed is None
