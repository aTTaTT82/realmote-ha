"""Sensor "Akku Fernbedienung" (v0.14.0).

Der Hub meldet den Ladestand retained auf realmote/<id>/akku = 0..100 (Firmware >= 4.81.64). Er uebernimmt ihn
einmal am Tag aus den Funkpaketen (der Wert wackelt unter Sendelast) -- der Sensor aendert sich also selten.
Mit mehreren Fernbedienungen an einem Hub zeigt er den Wert, den der Hub zuletzt uebernommen hat -- von der
Fernbedienung, die nach dem Neustart des Hubs bzw. nach Ablauf des Tages als erste gefunkt hat. Fuer eine
Warnung bei niedrigem Stand gibt es einen Blueprint im Repo.
"""
from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BASE_TOPIC, CONF_DEVICE_ID, DEFAULT_BASE_TOPIC, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([RealMoteBatterySensor(entry)])


class RealMoteBatterySensor(SensorEntity):
    """Ladestand der Funk-Fernbedienung in Prozent."""

    _attr_has_entity_name = True
    _attr_name = "Akku Fernbedienung"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry) -> None:
        self._device_id: str = entry.data[CONF_DEVICE_ID]
        self._base: str = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
        self._attr_native_value = None
        self._attr_unique_id = f"{self._device_id}_akku"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._device_id)})

    async def async_added_to_hass(self) -> None:
        @callback
        def _on_akku(msg: mqtt.ReceiveMessage) -> None:
            try:
                wert = int(str(msg.payload).strip())
            except (TypeError, ValueError):
                return
            if 0 <= wert <= 100:
                self._attr_native_value = wert
                self.async_write_ha_state()

        self.async_on_remove(
            await mqtt.async_subscribe(
                self.hass, f"{self._base}/{self._device_id}/akku", _on_akku
            )
        )
