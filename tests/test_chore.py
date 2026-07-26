"""Unit tests for the pure due-detection state machine."""
from datetime import date

import pytest

from custom_components.chores.chore import Chore, ChoreMode


def test_cycle_chore_not_due_below_threshold():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=29)
    assert chore.is_due(date(2026, 1, 1)) is False


def test_cycle_chore_due_at_threshold():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=30)
    assert chore.is_due(date(2026, 1, 1)) is True


def test_cycle_chore_stays_due_above_threshold():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=45)
    assert chore.is_due(date(2026, 1, 1)) is True


def test_log_cycle_increments_count():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=29)
    chore.log_cycle()
    assert chore.count == 30
    assert chore.is_due(date(2026, 1, 1)) is True


def test_log_cycle_rejected_for_interval_mode():
    chore = Chore("c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7)
    with pytest.raises(ValueError):
        chore.log_cycle()


def test_interval_chore_due_when_never_completed():
    chore = Chore("c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7)
    assert chore.is_due(date(2026, 1, 1)) is True


def test_interval_chore_not_due_before_interval_elapses():
    chore = Chore(
        "c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7,
        last_completed=date(2026, 1, 1),
    )
    assert chore.is_due(date(2026, 1, 5)) is False


def test_interval_chore_due_exactly_on_interval_boundary():
    chore = Chore(
        "c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7,
        last_completed=date(2026, 1, 1),
    )
    assert chore.is_due(date(2026, 1, 8)) is True


def test_should_notify_today_dedup():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=30)
    today = date(2026, 1, 1)
    assert chore.should_notify_today(today) is True
    chore.record_notified(today)
    assert chore.should_notify_today(today) is False


def test_should_notify_today_resets_next_day():
    chore = Chore(
        "c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30,
        count=30, last_notified_date=date(2026, 1, 1),
    )
    assert chore.should_notify_today(date(2026, 1, 2)) is True


def test_mark_complete_resets_cycle_chore():
    chore = Chore(
        "c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30,
        count=35, last_notified_date=date(2026, 1, 1),
    )
    chore.mark_complete(date(2026, 1, 2))
    assert chore.count == 0
    assert chore.last_notified_date is None
    assert chore.is_due(date(2026, 1, 2)) is False


def test_mark_complete_reschedules_interval_chore_from_completion_date():
    chore = Chore(
        "c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7,
        last_completed=date(2026, 1, 1),
    )
    chore.mark_complete(date(2026, 1, 10))
    assert chore.last_completed == date(2026, 1, 10)
    assert chore.is_due(date(2026, 1, 16)) is False
    assert chore.is_due(date(2026, 1, 17)) is True
