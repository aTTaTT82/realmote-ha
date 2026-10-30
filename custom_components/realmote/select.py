"""Auswahl-Entity "Aktivität": zeigt die laufende Activity des Hubs und schaltet sie um (v0.14.0).

Der Hub meldet seine Activity retained auf realmote/<id>/aktivitaet = 0..3 (Firmware >= 4.81.64; 0 = Aus) --
damit sieht Home Assistant, was laeuft, auch wenn sie an der Fernbedienung, per Alexa oder in der Webremote
gewechselt wurde. Eine Auswahl schickt "activity:N" bzw. "alloff" auf realmote/<id>/cmd. Automationen
koennen auf den Zustand reagieren ("Filmabend startet -> Licht dimmen", siehe die Blueprints im Repo).
"""
from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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

AUS = "Aus"


def optionen(acts: object) -> list[str]:
    """["Aus", Name 1, Name 2, Name 3] -- eindeutig (HA verlangt das), ohne Namen "Activity N"."""
    namen = acts if isinstance(acts, list) else []
    out = [AUS]
    for i in range(NUM_ACTIVITIES):
        name = str(namen[i]).strip() if i < len(namen) and namen[i] else ""
        name = name or f"Activity {i + 1}"
        while name in out:
            name = f"{name} ({i + 1})"
        out.append(name)
    return out


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([RealMoteActivitySelect(entry)])


class RealMoteActivitySelect(SelectEntity):
    """Die laufende Activity des Hubs (Aus, 1..3)."""

    _attr_has_entity_name = True
    _attr_name = "Aktivität"
    _attr_icon = "mdi:remote-tv"

    def __init__(self, entry: ConfigEntry) -> None:
        self._device_id: str = entry.data[CONF_DEVICE_ID]
        self._base: str = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
        self._attr_options = optionen(entry.data.get(CONF_ACTS))
        self._attr_current_option = None
        self._attr_unique_id = f"{self._device_id}_aktivitaet"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._device_id)})

    async def async_added_to_hass(self) -> None:
        @callback
        def _on_aktivitaet(msg: mqtt.ReceiveMessage) -> None:
            try:
                n = int(str(msg.payload).strip())
            except (TypeError, ValueError):
                return
            if 0 <= n < len(self._attr_options):
                self._attr_current_option = self._attr_options[n]
                self.async_write_ha_state()

        self.async_on_remove(
            await mqtt.async_subscribe(
                self.hass, f"{self._base}/{self._device_id}/aktivitaet", _on_aktivitaet
            )
        )

    async def async_select_option(self, option: str) -> None:
        n = self._attr_options.index(option)
        await mqtt.async_publish(
            self.hass,
            f"{self._base}/{self._device_id}/cmd",
            "alloff" if n == 0 else f"activity:{n}",
        )
