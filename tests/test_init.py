"""Tests for Chores integration setup."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


async def test_setup_entry_succeeds(hass):
    """A config entry for the hub sets up successfully."""
    entry = MockConfigEntry(domain=DOMAIN, title="Chores & Maintenance", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_removed_chore_device_is_cleaned_up_on_reload(hass):
    """Removing a chore from options (as the options flow does) and reloading must
    remove that chore's device, not leave it orphaned as unavailable forever."""
    chore_one = {
        "name": "Dishwasher maintenance",
        "mode": "cycle_count",
        "cycle_threshold": 30,
        "completion_method": "notification_action",
        "notify_time": "08:00:00",
    }
    chore_two = {
        "name": "Water plants",
        "mode": "interval_days",
        "interval_days": 7,
        "completion_method": "notification_action",
        "notify_time": "08:00:00",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={"chores": {"c1": chore_one, "c2": chore_two}},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    assert device_registry.async_get_device({(DOMAIN, "c2")}) is not None

    hass.config_entries.async_update_entry(
        entry, options={"chores": {"c1": chore_one}}
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, "c2")}) is None
    assert device_registry.async_get_device({(DOMAIN, "c1")}) is not None
    assert device_registry.async_get_device({(DOMAIN, entry.entry_id)}) is not None
