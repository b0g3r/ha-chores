"""Binary sensor platform: per-chore due flag."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import ChoreUpdateMixin, chore_device_info
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ChoreDueBinarySensor(entry, chore_id, store) for chore_id in store.chores
    )


class ChoreDueBinarySensor(ChoreUpdateMixin, BinarySensorEntity):
    """True while a chore is due/overdue."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, chore_id: str, store: ChoreStore) -> None:
        self._chore_id = chore_id
        self._store = store
        chore = store.chores[chore_id]
        self._attr_unique_id = f"{chore_id}_due"
        self._attr_name = f"{chore.name} due"
        self._attr_device_info = chore_device_info(entry, chore_id, chore.name)

    @property
    def is_on(self) -> bool:
        return self._store.chores[self._chore_id].is_due(dt_util.now().date())
