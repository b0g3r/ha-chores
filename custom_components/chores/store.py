"""Runtime state persistence for chores (count, last_completed, last_notified_date)."""
from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .chore import Chore, ChoreMode
from .const import DOMAIN

STORAGE_VERSION = 1


def _chore_from_config(chore_id: str, config: dict[str, Any], state: dict[str, Any]) -> Chore:
    """Build a Chore by merging its options-provided shape with its stored runtime state."""
    last_completed = state.get("last_completed")
    last_notified_date = state.get("last_notified_date")
    return Chore(
        chore_id=chore_id,
        name=config["name"],
        mode=ChoreMode(config["mode"]),
        interval_days=config.get("interval_days"),
        cycle_threshold=config.get("cycle_threshold"),
        count=state.get("count", 0),
        last_completed=date.fromisoformat(last_completed) if last_completed else None,
        last_notified_date=date.fromisoformat(last_notified_date) if last_notified_date else None,
    )


def _state_from_chore(chore: Chore) -> dict[str, Any]:
    """Extract just the runtime fields of a Chore for persistence."""
    return {
        "count": chore.count,
        "last_completed": chore.last_completed.isoformat() if chore.last_completed else None,
        "last_notified_date": chore.last_notified_date.isoformat() if chore.last_notified_date else None,
    }


class ChoreStore:
    """Loads/saves chore runtime state and holds the live Chore objects for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}_state")
        self.chores: dict[str, Chore] = {}

    async def async_load(self, chore_configs: dict[str, dict[str, Any]]) -> None:
        """Rebuild self.chores from the given options-provided configs plus any stored state."""
        raw_state: dict[str, Any] = await self._store.async_load() or {}
        self.chores = {
            chore_id: _chore_from_config(chore_id, config, raw_state.get(chore_id, {}))
            for chore_id, config in chore_configs.items()
        }

    async def async_save(self) -> None:
        """Persist the runtime fields of every current chore."""
        await self._store.async_save(
            {chore_id: _state_from_chore(chore) for chore_id, chore in self.chores.items()}
        )
