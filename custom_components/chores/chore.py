"""Pure due-detection state machine for a single chore. No Home Assistant imports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class ChoreMode(str, Enum):
    INTERVAL_DAYS = "interval_days"
    CYCLE_COUNT = "cycle_count"


@dataclass
class Chore:
    chore_id: str
    name: str
    mode: ChoreMode
    interval_days: int | None = None
    cycle_threshold: int | None = None
    count: int = 0
    last_completed: date | None = None
    last_notified_date: date | None = None

    def __post_init__(self) -> None:
        if self.mode is ChoreMode.INTERVAL_DAYS and self.interval_days is None:
            raise ValueError("interval_days is required when mode is interval_days")
        if self.mode is ChoreMode.CYCLE_COUNT and self.cycle_threshold is None:
            raise ValueError("cycle_threshold is required when mode is cycle_count")

    def is_due(self, today: date) -> bool:
        """Whether this chore currently needs attention."""
        if self.mode is ChoreMode.CYCLE_COUNT:
            return self.count >= self.cycle_threshold
        if self.last_completed is None:
            return True
        return today >= self.last_completed + timedelta(days=self.interval_days)

    def should_notify_today(self, today: date) -> bool:
        """Due, and not already notified today (the dedup rule, spec §10)."""
        return self.is_due(today) and self.last_notified_date != today

    def record_notified(self, today: date) -> None:
        self.last_notified_date = today

    def log_cycle(self) -> None:
        """Record one completed cycle. Only valid for cycle-count-mode chores."""
        if self.mode is not ChoreMode.CYCLE_COUNT:
            raise ValueError(f"log_cycle is not valid for mode {self.mode}")
        self.count += 1

    def mark_complete(self, today: date) -> None:
        """Reset the chore after completion, regardless of mode."""
        self.count = 0
        self.last_completed = today
        self.last_notified_date = None
