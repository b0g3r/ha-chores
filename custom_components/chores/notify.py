"""Sending and clearing due-notifications (spec §10)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .chore import Chore
from .const import (
    CONF_CHORES,
    CONF_MESSAGE,
    CONF_NOTIFICATION_ENABLED,
    CONF_PERSON_NOTIFY_MAP,
    NOTIFICATION_ACTION_PREFIX,
)


def notification_tag(chore_id: str) -> str:
    """Stable per-chore notification tag, used both to send and to clear (spec §10)."""
    return f"chores_{chore_id}"


def _notify_service_name(notify_entity_id: str) -> str:
    """'notify.alex_phone' -> 'alex_phone', the service name under the notify domain."""
    return notify_entity_id.split(".", 1)[1]


async def async_send_due_notification(
    hass: HomeAssistant, entry: ConfigEntry, chore: Chore
) -> None:
    """Notify everyone currently home, mapped via the hub's person->notify options."""
    person_notify_map: dict[str, str] = entry.options.get(CONF_PERSON_NOTIFY_MAP, {})
    chore_config = entry.options.get(CONF_CHORES, {}).get(chore.chore_id, {})
    message = chore_config.get(CONF_MESSAGE) or f"{chore.name} is due."
    tag = notification_tag(chore.chore_id)
    data: dict = {"tag": tag, "sticky": True}
    if chore_config.get(CONF_NOTIFICATION_ENABLED):
        data["actions"] = [
            {
                "action": f"{NOTIFICATION_ACTION_PREFIX}{chore.chore_id}",
                "title": "Mark done",
            }
        ]
    for person_entity_id, notify_entity_id in person_notify_map.items():
        if "." not in notify_entity_id:
            continue  # malformed mapping entry; don't let it abort the others
        state = hass.states.get(person_entity_id)
        if state is None or state.state != "home":
            continue
        await hass.services.async_call(
            "notify",
            _notify_service_name(notify_entity_id),
            {
                "title": chore.name,
                "message": message,
                "data": data,
            },
        )


async def async_clear_due_notification(
    hass: HomeAssistant, entry: ConfigEntry, chore_id: str
) -> None:
    """Clear a chore's due-notification on every mapped target, not just those home."""
    person_notify_map: dict[str, str] = entry.options.get(CONF_PERSON_NOTIFY_MAP, {})
    tag = notification_tag(chore_id)
    for notify_entity_id in person_notify_map.values():
        if "." not in notify_entity_id:
            continue  # malformed mapping entry; don't let it abort the others
        await hass.services.async_call(
            "notify",
            _notify_service_name(notify_entity_id),
            {"message": "clear_notification", "data": {"tag": tag}},
        )
