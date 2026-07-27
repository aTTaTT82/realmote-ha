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


# Ausfuehrbare Einzel-Tasten (Hub-Cmd "key:<NAME>", Firmware >= 4.13.0).
# (label, icon, standardmaessig aktiviert?) — selten gebrauchte sind default AUS,
# damit die Geraeteseite uebersichtlich bleibt (in HA pro Entity aktivierbar).
SEND_KEYS: dict[str, tuple[str, str, bool]] = {
    "PLAY": ("Play senden", "mdi:play", True),
    "PAUSE": ("Pause senden", "mdi:pause", True),
    "STOP": ("Stopp senden", "mdi:stop", True),
    "REWIND": ("Zurückspulen senden", "mdi:rewind", True),
    "FORWARD": ("Vorspulen senden", "mdi:fast-forward", True),
    "VOL_UP": ("Lautstärke + senden", "mdi:volume-plus", True),
    "VOL_DOWN": ("Lautstärke − senden", "mdi:volume-minus", True),
    "MUTE": ("Stumm senden", "mdi:volume-mute", True),
    "CH_UP": ("Kanal + senden", "mdi:chevron-up-box", True),
    "CH_DOWN": ("Kanal − senden", "mdi:chevron-down-box", True),
    "POWER": ("Power senden", "mdi:power-cycle", True),
    "OK": ("OK senden", "mdi:checkbox-marked-circle-outline", False),
    "UP": ("Hoch senden", "mdi:arrow-up-bold", False),
    "DOWN": ("Runter senden", "mdi:arrow-down-bold", False),
    "LEFT": ("Links senden", "mdi:arrow-left-bold", False),
    "RIGHT": ("Rechts senden", "mdi:arrow-right-bold", False),
    "BACK": ("Zurück senden", "mdi:arrow-u-left-top", False),
    "EXIT": ("Exit senden", "mdi:close-box-outline", False),
    "MENU": ("Menü senden", "mdi:menu", False),
    "INFO": ("Info senden", "mdi:information-outline", False),
    "GUIDE": ("Guide senden", "mdi:television-guide", False),
    "DVR": ("DVR senden", "mdi:record-rec", False),
    "REC": ("Aufnahme senden", "mdi:record", False),
    "RED": ("Rot senden", "mdi:square-rounded", False),
    "GREEN": ("Grün senden", "mdi:square-rounded", False),
    "YELLOW": ("Gelb senden", "mdi:square-rounded", False),
    "BLUE": ("Blau senden", "mdi:square-rounded", False),
    "HDMI1": ("HDMI 1 senden", "mdi:hdmi-port", False),
    "HDMI2": ("HDMI 2 senden", "mdi:hdmi-port", False),
    "HDMI3": ("HDMI 3 senden", "mdi:hdmi-port", False),
    "HDMI4": ("HDMI 4 senden", "mdi:hdmi-port", False),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Je Activity einen Knopf + "Alles aus" + ausfuehrbare Einzel-Tasten anlegen."""
    device_id: str = entry.data[CONF_DEVICE_ID]
    base: str = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)

    # Namen kommen aus dem Hub-Announce (Firmware >= 4.11.0); Fallback = generisch.
    acts = entry.data.get(CONF_ACTS) or [f"Activity {i}" for i in range(1, NUM_ACTIVITIES + 1)]

    entities: list[ButtonEntity] = [
        RealMoteActivityButton(device_id, base, i + 1, name)
        for i, name in enumerate(acts[:NUM_ACTIVITIES])
    ]
    entities.append(RealMoteActivityButton(device_id, base, 0, "Alles aus"))
    entities.extend(
        RealMoteKeyButton(device_id, base, key, label, icon, enabled)
        for key, (label, icon, enabled) in SEND_KEYS.items()
    )
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


class RealMoteKeyButton(ButtonEntity):
    """Ein Druck = diese Fernbedienungs-Taste ausfuehren (Activity-bewusst).

    "Pause senden" pausiert also genau das Geraet, das laut aktueller Activity
    gerade die Wiedergabe macht — identisch zu einem Druck auf der Fernbedienung.
    """

    _attr_has_entity_name = True

    def __init__(
        self, device_id: str, base: str, key: str, label: str, icon: str, enabled: bool
    ) -> None:
        self._device_id = device_id
        self._base = base
        self._key = key
        self._attr_name = label
        self._attr_unique_id = f"{device_id}_send_{key.lower()}"
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    async def async_press(self) -> None:
        await mqtt.async_publish(
            self.hass, f"{self._base}/{self._device_id}/cmd", f"key:{self._key}"
        )
