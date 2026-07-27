"""Tests for the shared due-check routine and its dedup behavior."""
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import CONF_PERSON_NOTIFY_MAP, DOMAIN
from custom_components.chores.due_check import (
    async_run_due_check,
    async_schedule_daily_checks,
)
from custom_components.chores.store import ChoreStore


async def _setup_entry_with_one_chore(hass, chores):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={CONF_PERSON_NOTIFY_MAP: {}, "chores": chores},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _setup_entry_with_due_chore(hass):
    entry = await _setup_entry_with_one_chore(
        hass,
        {
            "c1": {
                "name": "Dishwasher maintenance",
                "mode": "cycle_count",
                "cycle_threshold": 30,
                "nfc_enabled": False,
                "notification_enabled": True,
                "notify_enabled": True,
                "notify_time": "08:00:00",
            }
        },
    )
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


async def test_due_check_skips_weekday_when_weekends_only_is_set(hass):
    """weekends_only must suppress the notification (and not mark it as sent) on a
    weekday, so it's still due and unnotified once the weekend actually arrives."""
    entry = await _setup_entry_with_one_chore(
        hass,
        {
            "c1": {
                "name": "Dishwasher maintenance",
                "mode": "cycle_count",
                "cycle_threshold": 30,
                "nfc_enabled": False,
                "notification_enabled": True,
                "notify_enabled": True,
                "notify_time": "08:00:00",
                "weekends_only": True,
            }
        },
    )
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]

    with patch(
        "custom_components.chores.due_check.async_send_due_notification",
        new=AsyncMock(),
    ) as send_mock:
        with patch(
            "custom_components.chores.due_check.dt_util.now",
            return_value=datetime(2026, 7, 28),  # a Tuesday
        ):
            await async_run_due_check(hass, entry, "c1")
        assert send_mock.await_count == 0
        assert store.chores["c1"].last_notified_date is None

        with patch(
            "custom_components.chores.due_check.dt_util.now",
            return_value=datetime(2026, 8, 1),  # a Saturday
        ):
            await async_run_due_check(hass, entry, "c1")
        assert send_mock.await_count == 1
        assert store.chores["c1"].last_notified_date == date(2026, 8, 1)


async def test_log_cycle_service_triggers_immediate_due_check(hass):
    """_handle_log_cycle (services.py) must call the shared due-check right after
    incrementing — this is what makes a cycle-mode chore notify immediately on the
    cycle that crosses its threshold, not just at the next morning's scheduled check."""
    entry = await _setup_entry_with_one_chore(
        hass,
        {
            "c1": {
                "name": "Dishwasher maintenance",
                "mode": "cycle_count",
                "cycle_threshold": 30,
                "nfc_enabled": False,
                "notification_enabled": True,
                "notify_enabled": True,
                "notify_time": "08:00:00",
            }
        },
    )

    with patch(
        "custom_components.chores.services.async_run_due_check", new=AsyncMock()
    ) as due_check_mock:
        for _ in range(30):
            await hass.services.async_call(
                DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True
            )

    assert due_check_mock.await_count == 30
    due_check_mock.assert_awaited_with(hass, entry, "c1")


async def test_schedule_daily_checks_registers_one_tracker_per_chore_at_its_time(hass):
    """async_schedule_daily_checks must wire each chore to its own notify_time, not a
    shared/default time — a dropped or mis-parsed per-chore time would still pass a
    test that only checks the callback count."""
    entry = await _setup_entry_with_one_chore(
        hass,
        {
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
                "name": "Water the plants",
                "mode": "interval_days",
                "interval_days": 3,
                "nfc_enabled": False,
                "notification_enabled": True,
                "notify_enabled": True,
                "notify_time": "19:30:15",
            },
        },
    )

    with patch(
        "custom_components.chores.due_check.async_track_time_change"
    ) as track_mock:
        track_mock.return_value = lambda: None
        unsubs = async_schedule_daily_checks(hass, entry)

    assert len(unsubs) == 2
    assert track_mock.call_count == 2
    registered_times = [call.kwargs for call in track_mock.call_args_list]
    assert {"hour": 8, "minute": 0, "second": 0} in registered_times
    assert {"hour": 19, "minute": 30, "second": 15} in registered_times


async def test_schedule_daily_checks_skips_chores_with_reminders_disabled(hass):
    entry = await _setup_entry_with_one_chore(
        hass,
        {
            "c1": {
                "name": "Dishwasher maintenance",
                "mode": "cycle_count",
                "cycle_threshold": 30,
                "nfc_enabled": False,
                "notification_enabled": True,
                "notify_enabled": False,
            },
        },
    )

    with patch(
        "custom_components.chores.due_check.async_track_time_change"
    ) as track_mock:
        unsubs = async_schedule_daily_checks(hass, entry)

    assert unsubs == []
    assert track_mock.call_count == 0
