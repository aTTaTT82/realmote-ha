"""Knopf-Entities: die Activities des Hubs aus HA starten.

Damit lassen sich Hub-Activities (z. B. "Android TV" = TV an + HDMI + Soundbar +
BLE-Wake) in HA-Skripte, Automationen und Dashboards einbauen — z. B. ein Skript
"Filmabend" = Licht-Szene aktivieren + Activity starten, gelegt auf eine
Smart-Home-Taste der Fernbedienung.

Der Druck publiziert auf realmote/<id>/cmd: "activity:1..3" bzw. "alloff"
(Hub-Firmware >= 4.11.0 fuer activity:N; alloff geht seit 4.7.1).
"""
from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACTS,
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    NUM_ACTIVITIES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Je Activity einen Knopf + "Alles aus" anlegen."""
    device_id: str = entry.data[CONF_DEVICE_ID]
    base: str = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)

    # Namen kommen aus dem Hub-Announce (Firmware >= 4.11.0); Fallback = generisch.
    acts = entry.data.get(CONF_ACTS) or [f"Activity {i}" for i in range(1, NUM_ACTIVITIES + 1)]

    entities: list[ButtonEntity] = [
        RealMoteActivityButton(device_id, base, i + 1, name)
        for i, name in enumerate(acts[:NUM_ACTIVITIES])
    ]
    entities.append(RealMoteActivityButton(device_id, base, 0, "Alles aus"))
    async_add_entities(entities)


class RealMoteActivityButton(ButtonEntity):
    """Ein Druck = Hub-Activity starten (bzw. alles ausschalten)."""

    _attr_has_entity_name = True

    def __init__(self, device_id: str, base: str, number: int, name: str) -> None:
        self._device_id = device_id
        self._base = base
        self._number = number  # 1..3 = Activity, 0 = "Alles aus"
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_activity_{number}"
        self._attr_icon = "mdi:power" if number == 0 else "mdi:play-circle-outline"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    async def async_press(self) -> None:
        payload = "alloff" if self._number == 0 else f"activity:{self._number}"
        await mqtt.async_publish(
            self.hass, f"{self._base}/{self._device_id}/cmd", payload
        )
