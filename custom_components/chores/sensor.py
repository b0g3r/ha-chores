"""Sensor platform: per-chore status."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, chore_updated_signal
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ChoreStatusSensor(entry, chore_id, store) for chore_id in store.chores
    )


class ChoreStatusSensor(SensorEntity):
    """Reports whether a chore is ok or due."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, chore_id: str, store: ChoreStore) -> None:
        self._chore_id = chore_id
        self._store = store
        chore = store.chores[chore_id]
        self._attr_unique_id = f"{chore_id}_status"
        self._attr_name = f"{chore.name} status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, chore_id)},
            name=chore.name,
            via_device=(DOMAIN, entry.entry_id),
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                chore_updated_signal(self._chore_id),
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self) -> str:
        chore = self._store.chores[self._chore_id]
        return "due" if chore.is_due(dt_util.now().date()) else "ok"

    @property
    def extra_state_attributes(self) -> dict:
        chore = self._store.chores[self._chore_id]
        last_completed = (
            chore.last_completed.isoformat() if chore.last_completed else None
        )
        return {
            "chore_id": self._chore_id,
            "last_completed": last_completed,
            "count": chore.count,
            "cycle_threshold": chore.cycle_threshold,
            "interval_days": chore.interval_days,
        }
