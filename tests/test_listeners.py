"""Tests for NFC tag and notification-action completion wiring."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import (
    CONF_CHORES,
    DOMAIN,
    NOTIFICATION_ACTION_PREFIX,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry(
    hass, *, nfc_tag_entity_id: str, completion_method: str = "both"
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            CONF_CHORES: {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": completion_method,
                    "nfc_tag_entity_id": nfc_tag_entity_id,
                    "notify_time": "08:00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30
    return entry


async def test_tag_scanned_completes_matching_chore(hass):
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    registry.async_get_or_create(
        "tag", "tag", "test-tag-unique-id", suggested_object_id="dishwasher_maintenance"
    )
    entry = await _setup_entry(hass, nfc_tag_entity_id="tag.dishwasher_maintenance")

    hass.bus.async_fire("tag_scanned", {"tag_id": "test-tag-unique-id"})
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]
    assert store.chores["c1"].count == 0


async def test_notification_action_completes_matching_chore(hass):
    entry = await _setup_entry(hass, nfc_tag_entity_id="")

    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"{NOTIFICATION_ACTION_PREFIX}c1"}
    )
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]
    assert store.chores["c1"].count == 0


async def test_tag_scanned_does_not_complete_notification_action_only_chore(hass):
    """A chore configured for notification_action only must not be completable by a
    tag scan, even if its (unused) nfc_tag_entity_id happens to match the scanned
    tag."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    registry.async_get_or_create(
        "tag", "tag", "test-tag-unique-id", suggested_object_id="dishwasher_maintenance"
    )
    entry = await _setup_entry(
        hass,
        nfc_tag_entity_id="tag.dishwasher_maintenance",
        completion_method="notification_action",
    )

    hass.bus.async_fire("tag_scanned", {"tag_id": "test-tag-unique-id"})
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]
    assert store.chores["c1"].count == 30
