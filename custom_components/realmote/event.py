"""Event-Entities: JEDE Taste der Fernbedienung als HA-Ereignis.

Der Hub publiziert ab Firmware 4.12.0 jeden Tastendruck (ausser den Smart-Home-
Tasten 1-6, die haben ihre eigenen 12 Aktions-Slots) zusaetzlich auf
realmote/<id>/key = <Tastenname> — nur die Druck-Flanke, kein Repeat beim Halten.
Die normale Tastenfunktion (IR/BLE/Activity) laeuft unveraendert weiter; die
Events kommen "on top" und machen jede Taste in HA-Automationen nutzbar.
"""
from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.event import EventDeviceClass, EventEntity
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

# Reihenfolge = Anzeige-Reihenfolge am Geraet; Werte = deutsche Anzeigenamen.
# ACT_1..3 bekommen ihre Namen live aus dem Hub-Announce (acts).
KEY_LABELS: dict[str, str] = {
    "RED": "Taste Rot",
    "GREEN": "Taste Grün",
    "YELLOW": "Taste Gelb",
    "BLUE": "Taste Blau",
    "UP": "Taste Hoch",
    "DOWN": "Taste Runter",
    "LEFT": "Taste Links",
    "RIGHT": "Taste Rechts",
    "OK": "Taste OK",
    "DVR": "Taste DVR",
    "GUIDE": "Taste Guide",
    "INFO": "Taste Info",
    "EXIT": "Taste Exit",
    "MENU": "Taste Menü",
    "VOL_UP": "Taste Lautstärke +",
    "VOL_DOWN": "Taste Lautstärke −",
    "CH_UP": "Taste Kanal +",
    "CH_DOWN": "Taste Kanal −",
    "MUTE": "Taste Stumm",
    "BACK": "Taste Zurück",
    "REWIND": "Taste Zurückspulen",
    "PLAY": "Taste Play",
    "FORWARD": "Taste Vorspulen",
    "REC": "Taste Aufnahme",
    "PAUSE": "Taste Pause",
    "STOP": "Taste Stopp",
    "ACT_1": "Taste Activity 1",
    "ACT_2": "Taste Activity 2",
    "ACT_3": "Taste Activity 3",
    "ACT_OFF": "Taste Aus",
    "POWER_TV": "Taste Power TV",
    "POWER_SOUNDBAR": "Taste Power Soundbar",
    "POWER_RECEIVER": "Taste Power Receiver",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Je Fernbedienungs-Taste eine Event-Entity + EIN gemeinsames MQTT-Abo."""
    device_id: str = entry.data[CONF_DEVICE_ID]
    base: str = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
    acts = entry.data.get(CONF_ACTS) or []

    labels = dict(KEY_LABELS)
    for i in range(min(len(acts), NUM_ACTIVITIES)):
        labels[f"ACT_{i + 1}"] = f"Taste Activity {acts[i]}"

    entities: dict[str, RealMoteKeyEvent] = {
        key: RealMoteKeyEvent(device_id, key, label) for key, label in labels.items()
    }
    async_add_entities(entities.values())

    @callback
    def _on_key(msg: mqtt.ReceiveMessage) -> None:
        ent = entities.get(str(msg.payload).strip())
        if ent:
            ent.handle_press()

    entry.async_on_unload(
        await mqtt.async_subscribe(hass, f"{base}/{device_id}/key", _on_key)
    )


class RealMoteKeyEvent(EventEntity):
    """Eine Fernbedienungs-Taste als Ereignis (Event-Typ: press)."""

    _attr_has_entity_name = True
    _attr_event_types = ["press"]
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(self, device_id: str, key: str, label: str) -> None:
        self._attr_name = label
        self._attr_unique_id = f"{device_id}_key_{key.lower()}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @callback
    def handle_press(self) -> None:
        if self.hass is None:
            return
        self._trigger_event("press")
        self.async_write_ha_state()
