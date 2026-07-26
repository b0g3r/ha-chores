"""A single to-do list entity showing every currently-due chore (spec §11)."""
from __future__ import annotations

from datetime import date

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, chore_updated_signal
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ActiveChoresTodoList(entry, store)])


class ActiveChoresTodoList(TodoListEntity):
    """Lists every chore that is currently due/overdue.

    Read-only: items are driven by chore due-state (Task 1-7), not by user
    checkboxes, so no UPDATE_TODO_ITEM feature.
    """

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, store: ChoreStore) -> None:
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_chores_todo"
        self._attr_name = "Chores"

    async def async_added_to_hass(self) -> None:
        for chore_id in self._store.chores:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass, chore_updated_signal(chore_id), self.async_write_ha_state
                )
            )

    @property
    def todo_items(self) -> list[TodoItem]:
        today = date.today()
        return [
            TodoItem(
                uid=chore_id, summary=chore.name, status=TodoItemStatus.NEEDS_ACTION
            )
            for chore_id, chore in self._store.chores.items()
            if chore.is_due(today)
        ]
