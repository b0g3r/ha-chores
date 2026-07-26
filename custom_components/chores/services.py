"""Services for the Chores & Maintenance integration."""
from __future__ import annotations

from datetime import date

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, chore_updated_signal
from .notify import async_clear_due_notification
from .store import ChoreStore

SERVICE_LOG_CYCLE = "log_cycle"
SERVICE_MARK_COMPLETE = "mark_complete"

_CHORE_ID_SCHEMA = vol.Schema({vol.Required("chore_id"): cv.string})


def _get_entry_and_store(hass: HomeAssistant) -> tuple[ConfigEntry, ChoreStore]:
    """The hub is single-instance (config_flow.py enforces `single_instance_allowed`),
    so there's always exactly one entry — no per-chore search across entries needed."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return entry, hass.data[DOMAIN][entry.entry_id]


async def async_notify_chore_updated(hass: HomeAssistant, chore_id: str) -> None:
    """Persist and push an update for one chore. Shared by services and listeners."""
    _, store = _get_entry_and_store(hass)
    await store.async_save()
    async_dispatcher_send(hass, chore_updated_signal(chore_id))


async def async_complete_chore(hass: HomeAssistant, chore_id: str) -> None:
    """Completion routine shared by the service, NFC, and notification-action paths."""
    entry, store = _get_entry_and_store(hass)
    if chore_id not in store.chores:
        raise ServiceValidationError(f"Unknown chore_id: {chore_id}")
    store.chores[chore_id].mark_complete(date.today())
    await async_notify_chore_updated(hass, chore_id)
    await async_clear_due_notification(hass, entry, chore_id)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register chores.log_cycle and chores.mark_complete, once per HA instance."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_CYCLE):
        return

    async def _handle_log_cycle(call: ServiceCall) -> None:
        chore_id = call.data["chore_id"]
        _, store = _get_entry_and_store(hass)
        if chore_id not in store.chores:
            raise ServiceValidationError(f"Unknown chore_id: {chore_id}")
        store.chores[chore_id].log_cycle()
        await async_notify_chore_updated(hass, chore_id)

    async def _handle_mark_complete(call: ServiceCall) -> None:
        await async_complete_chore(hass, call.data["chore_id"])

    hass.services.async_register(
        DOMAIN, SERVICE_LOG_CYCLE, _handle_log_cycle, schema=_CHORE_ID_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_COMPLETE, _handle_mark_complete, schema=_CHORE_ID_SCHEMA
    )
