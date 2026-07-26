"""Tests for the shared due-check routine and its dedup behavior."""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import CONF_PERSON_NOTIFY_MAP, DOMAIN
from custom_components.chores.due_check import async_run_due_check
from custom_components.chores.store import ChoreStore


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry_with_due_chore(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            CONF_PERSON_NOTIFY_MAP: {},
            "chores": {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                }
            },
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30
    return entry


async def test_due_check_sends_once_and_records_notified_date(hass):
    entry = await _setup_entry_with_due_chore(hass)
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]

    with patch(
        "custom_components.chores.due_check.async_send_due_notification",
        new=AsyncMock(),
    ) as send_mock:
        await async_run_due_check(hass, entry, "c1")
        assert send_mock.await_count == 1
        assert store.chores["c1"].last_notified_date == date.today()

        await async_run_due_check(hass, entry, "c1")
        assert send_mock.await_count == 1  # dedup: not sent again the same day
