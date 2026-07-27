"""Services for the Chores & Maintenance integration."""
from __future__ import annotations

from datetime import date

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SERVICE_LOG_CYCLE,
    SERVICE_MARK_COMPLETE,
    chore_updated_signal,
)
from .due_check import async_run_due_check
from .notify import async_clear_due_notification
from .store import ChoreStore

_CHORE_ID_SCHEMA = vol.Schema({vol.Required("chore_id"): cv.string})
_MARK_COMPLETE_SCHEMA = vol.Schema(
    {vol.Required("chore_id"): cv.string, vol.Optional("completed_on"): cv.date}
)


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


async def async_complete_chore(
    hass: HomeAssistant, chore_id: str, completed_on: date | None = None
) -> None:
    """Completion routine shared by the service, NFC, and notification-action paths."""
    entry, store = _get_entry_and_store(hass)
    if chore_id not in store.chores:
        raise ServiceValidationError(f"Unknown chore_id: {chore_id}")
    store.chores[chore_id].mark_complete(completed_on or dt_util.now().date())
    await async_notify_chore_updated(hass, chore_id)
    await async_clear_due_notification(hass, entry, chore_id)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register chores.log_cycle and chores.mark_complete, once per HA instance."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_CYCLE):
        return

    async def _handle_log_cycle(call: ServiceCall) -> None:
        chore_id = call.data["chore_id"]
        entry, store = _get_entry_and_store(hass)
        if chore_id not in store.chores:
            raise ServiceValidationError(f"Unknown chore_id: {chore_id}")
        try:
            store.chores[chore_id].log_cycle()
        except ValueError as err:
            raise ServiceValidationError(
                f"Chore {chore_id} is not a cycle-count chore"
            ) from err
        await async_notify_chore_updated(hass, chore_id)
        await async_run_due_check(hass, entry, chore_id)

    async def _handle_mark_complete(call: ServiceCall) -> None:
        await async_complete_chore(
            hass, call.data["chore_id"], call.data.get("completed_on")
        )

    hass.services.async_register(
        DOMAIN, SERVICE_LOG_CYCLE, _handle_log_cycle, schema=_CHORE_ID_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_COMPLETE,
        _handle_mark_complete,
        schema=_MARK_COMPLETE_SCHEMA,
    )
