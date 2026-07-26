"""Tests for due-notification sending and clearing."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.chore import Chore, ChoreMode
from custom_components.chores.const import CONF_PERSON_NOTIFY_MAP, DOMAIN
from custom_components.chores.notify import (
    async_clear_due_notification,
    async_send_due_notification,
    notification_tag,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _entry_with_mapping(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={CONF_PERSON_NOTIFY_MAP: {"person.alex": "notify.alex_phone"}},
    )
    entry.add_to_hass(hass)
    return entry


def _register_fake_notify_service(hass, calls):
    """Register a real service under notify.alex_phone that records each call's data,
    so async_call goes through HA's actual service-dispatch machinery (ServiceRegistry
    uses __slots__ and can't be instance-monkeypatched)."""

    async def _handler(call):
        calls.append(call.data)

    hass.services.async_register("notify", "alex_phone", _handler)


async def test_send_due_notification_targets_only_people_home(hass):
    entry = _entry_with_mapping(hass)
    hass.states.async_set("person.alex", "home")
    calls = []
    _register_fake_notify_service(hass, calls)

    chore = Chore(
        "c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30,
        count=30,
    )
    await async_send_due_notification(hass, entry, chore)

    assert len(calls) == 1
    data = calls[0]
    assert data["data"]["tag"] == notification_tag("c1")
    assert "Dishwasher maintenance" in data["message"]


async def test_send_due_notification_skips_people_not_home(hass):
    entry = _entry_with_mapping(hass)
    hass.states.async_set("person.alex", "not_home")
    calls = []
    _register_fake_notify_service(hass, calls)

    chore = Chore(
        "c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30,
        count=30,
    )
    await async_send_due_notification(hass, entry, chore)

    assert calls == []


async def test_clear_due_notification_targets_everyone_mapped_regardless_of_presence(
    hass,
):
    entry = _entry_with_mapping(hass)
    hass.states.async_set("person.alex", "not_home")
    calls = []
    _register_fake_notify_service(hass, calls)

    await async_clear_due_notification(hass, entry, "c1")

    assert len(calls) == 1
    data = calls[0]
    assert data["message"] == "clear_notification"
    assert data["data"]["tag"] == notification_tag("c1")
