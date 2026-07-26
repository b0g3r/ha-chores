"""Button platform: manual mark-complete per chore."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SERVICE_MARK_COMPLETE
from .entity import chore_device_info
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ChoreMarkCompleteButton(entry, chore_id, store) for chore_id in store.chores
    )


class ChoreMarkCompleteButton(ButtonEntity):
    """Marks a chore complete on press, regardless of its completion method."""

    def __init__(self, entry: ConfigEntry, chore_id: str, store: ChoreStore) -> None:
        self._chore_id = chore_id
        chore = store.chores[chore_id]
        self._attr_unique_id = f"{chore_id}_mark_complete"
        self._attr_name = f"{chore.name} mark complete"
        self._attr_device_info = chore_device_info(entry, chore_id, chore.name)

    async def async_press(self) -> None:
        await self.hass.services.async_call(
            DOMAIN, SERVICE_MARK_COMPLETE, {"chore_id": self._chore_id}, blocking=True
        )
