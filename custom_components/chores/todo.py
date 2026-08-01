"""A single to-do list entity showing every currently-due chore (spec §11)."""
from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_MARK_COMPLETE, chore_updated_signal
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ActiveChoresTodoList(entry, store)])


class ActiveChoresTodoList(TodoListEntity):
    """Lists every chore that is currently due/overdue.

    The list itself is a computed view of chore due-state (Task 1-7), but
    checking an item off routes through the same mark_complete service the
    per-chore button uses, so it completes with today's date -- no
    backdating from the checkbox, matching the button's constraint.
    """

    _attr_should_poll = False
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

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
        today = dt_util.now().date()
        return [
            TodoItem(
                uid=chore_id, summary=chore.name, status=TodoItemStatus.NEEDS_ACTION
            )
            for chore_id, chore in self._store.chores.items()
            if chore.is_due(today)
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.status != TodoItemStatus.COMPLETED:
            return
        await self.hass.services.async_call(
            DOMAIN, SERVICE_MARK_COMPLETE, {"chore_id": item.uid}, blocking=True
        )
