"""Shared per-chore entity helpers: device linking and live-update wiring."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, chore_updated_signal


def chore_device_info(entry: ConfigEntry, chore_id: str, name: str) -> DeviceInfo:
    """DeviceInfo shared by every per-chore entity, linked to the hub device."""
    return DeviceInfo(
        identifiers={(DOMAIN, chore_id)},
        name=name,
        via_device=(DOMAIN, entry.entry_id),
    )


class ChoreUpdateMixin(Entity):
    """Pushes a state update whenever this entity's chore's runtime state changes."""

    _chore_id: str

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                chore_updated_signal(self._chore_id),
                self.async_write_ha_state,
            )
        )
