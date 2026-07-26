"""The Chores & Maintenance integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_CHORES, DOMAIN
from .due_check import async_schedule_daily_checks
from .listeners import async_register_listeners
from .services import async_register_services
from .store import ChoreStore

PLATFORMS: list[str] = ["sensor", "binary_sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Chores & Maintenance from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    store = ChoreStore(hass, entry.entry_id)
    await store.async_load(entry.options.get(CONF_CHORES, {}))
    hass.data[DOMAIN][entry.entry_id] = store

    await async_register_services(hass)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
    )

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    for unsub in async_schedule_daily_checks(hass, entry):
        entry.async_on_unload(unsub)

    for unsub in async_register_listeners(hass, entry):
        entry.async_on_unload(unsub)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change (e.g. a chore was added/removed)."""
    await hass.config_entries.async_reload(entry.entry_id)
