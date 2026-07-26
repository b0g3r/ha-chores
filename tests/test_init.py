"""Tests for Chores integration setup."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration loading for every test in this module."""
    yield


async def test_setup_entry_succeeds(hass):
    """A config entry for the hub sets up successfully."""
    entry = MockConfigEntry(domain=DOMAIN, title="Chores & Maintenance", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    from homeassistant.config_entries import ConfigEntryState
    assert entry.state is ConfigEntryState.LOADED
