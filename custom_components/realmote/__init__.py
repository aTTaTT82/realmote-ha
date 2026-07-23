"""RealMote – Tasten einer Funk-Fernbedienung auf HA-Geraete legen (per MQTT)."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ACTION,
    CONF_BASE_TOPIC,
    CONF_BRIGHTNESS,
    CONF_DEVICE_ID,
    CONF_ENTITY,
    CONF_NAME,
    CONF_POSITION,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen RealMote-Hub einrichten: MQTT-Taster-Event abonnieren."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT ist nicht verfuegbar – RealMote braucht die MQTT-Integration")
        return False

    device_id: str = entry.data[CONF_DEVICE_ID]
    base: str = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
    name: str = entry.data.get(CONF_NAME, device_id)

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer="RealMote",
        name=name,
        model="Universal Remote Hub",
    )

    topic = f"{base}/{device_id}/button"

    @callback
    def _on_button(msg: mqtt.ReceiveMessage) -> None:
        try:
            button = int(str(msg.payload).strip())
        except (ValueError, TypeError):
            return
        hass.async_create_task(_run_button(hass, entry, button))

    unsub = await mqtt.async_subscribe(hass, topic, _on_button)
    entry.async_on_unload(unsub)
    _LOGGER.info("RealMote %s: hoere auf %s", device_id, topic)
    return True


async def _run_button(hass: HomeAssistant, entry: ConfigEntry, button: int) -> None:
    """Die fuer diese Taste hinterlegte Aktion ausfuehren."""
    cfg = entry.options.get(str(button))
    if not cfg or not cfg.get(CONF_ENTITY):
        _LOGGER.debug("RealMote: Taste %s ist nicht belegt", button)
        return

    entity_id: str = cfg[CONF_ENTITY]
    action: str = cfg.get(CONF_ACTION, "toggle")
    domain = entity_id.split(".")[0]
    _LOGGER.debug("RealMote: Taste %s -> %s auf %s", button, action, entity_id)

    try:
        if action == "toggle":
            await hass.services.async_call(
                "homeassistant", "toggle", {"entity_id": entity_id}, blocking=False
            )
        elif action == "on":
            brightness = cfg.get(CONF_BRIGHTNESS)
            if brightness is not None and domain == "light":
                await hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": entity_id, "brightness_pct": int(brightness)},
                    blocking=False,
                )
            else:
                await hass.services.async_call(
                    "homeassistant", "turn_on", {"entity_id": entity_id}, blocking=False
                )
        elif action == "off":
            await hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": entity_id}, blocking=False
            )
        elif action == "open":
            await hass.services.async_call(
                "cover", "open_cover", {"entity_id": entity_id}, blocking=False
            )
        elif action == "close":
            await hass.services.async_call(
                "cover", "close_cover", {"entity_id": entity_id}, blocking=False
            )
        elif action == "position":
            await hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": entity_id, "position": int(cfg.get(CONF_POSITION, 0))},
                blocking=False,
            )
    except Exception:  # noqa: BLE001 – Service-Fehler nie den Callback killen lassen
        _LOGGER.exception("RealMote: Taste %s Aktion fehlgeschlagen", button)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Abmelden (unsubscribe passiert ueber entry.async_on_unload)."""
    return True
