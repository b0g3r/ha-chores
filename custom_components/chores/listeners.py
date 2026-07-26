"""Internal NFC-tag and notification-action completion wiring (spec §9)."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CHORES,
    CONF_NFC_ENABLED,
    CONF_NFC_TAG_ENTITY_ID,
    NOTIFICATION_ACTION_PREFIX,
)
from .services import async_complete_chore


def async_register_listeners(
    hass: HomeAssistant, entry: ConfigEntry
) -> list[Callable[[], None]]:
    """Subscribe to tag_scanned and mobile_app_notification_action for this entry."""

    async def _on_tag_scanned(event: Event) -> None:
        tag_id = event.data.get("tag_id")
        registry = er.async_get(hass)
        for chore_id, config in entry.options.get(CONF_CHORES, {}).items():
            if not config.get(CONF_NFC_ENABLED):
                continue
            nfc_entity_id = config.get(CONF_NFC_TAG_ENTITY_ID)
            if not nfc_entity_id:
                continue
            entity_entry = registry.async_get(nfc_entity_id)
            if entity_entry is not None and entity_entry.unique_id == tag_id:
                await async_complete_chore(hass, chore_id)

    async def _on_notification_action(event: Event) -> None:
        action = event.data.get("action", "")
        if not action.startswith(NOTIFICATION_ACTION_PREFIX):
            return
        chore_id = action[len(NOTIFICATION_ACTION_PREFIX):]
        if chore_id in entry.options.get(CONF_CHORES, {}):
            await async_complete_chore(hass, chore_id)

    return [
        hass.bus.async_listen("tag_scanned", _on_tag_scanned),
        hass.bus.async_listen(
            "mobile_app_notification_action", _on_notification_action
        ),
    ]
