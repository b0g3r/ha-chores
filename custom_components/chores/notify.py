"""Sending and clearing due-notifications (spec §10)."""
from __future__ import annotations

import logging

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

_LOGGER = logging.getLogger(__name__)


def notification_tag(chore_id: str) -> str:
    """Stable per-chore notification tag, used both to send and to clear (spec §10)."""
    return f"chores_{chore_id}"


def _resolve_notify_service(hass: HomeAssistant, notify_entity_id: str) -> str | None:
    """Find the callable notify service backing a notify entity picked in options.

    The person->notify mapping is filled via an EntitySelector(domain="notify"),
    which lists notify *entities* -- but rich data (tag/sticky/actions, needed for
    the "Mark done" action and for clearing) only works through the legacy
    per-target *service*. For mobile_app, that service is the entity's object_id
    prefixed with "mobile_app_" (e.g. entity notify.s25 -> service
    notify.mobile_app_s25); they're registered from the same device name but
    aren't the same string, so calling the object_id directly 404s. Fall back to
    the object_id itself for non-mobile_app targets, where it typically matches."""
    object_id = notify_entity_id.split(".", 1)[1]
    for candidate in (object_id, f"mobile_app_{object_id}"):
        if hass.services.has_service("notify", candidate):
            return candidate
    _LOGGER.warning("No notify service found for %s; skipping", notify_entity_id)
    return None


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
        service = _resolve_notify_service(hass, notify_entity_id)
        if service is None:
            continue
        await hass.services.async_call(
            "notify",
            service,
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
        service = _resolve_notify_service(hass, notify_entity_id)
        if service is None:
            continue
        await hass.services.async_call(
            "notify",
            service,
            {"message": "clear_notification", "data": {"tag": tag}},
        )
