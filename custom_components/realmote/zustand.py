"""Zustand der Geraete aus Home Assistant an den Hub melden (v0.14.0, Hub-Firmware >= 4.81.64).

Der Hub weiss nicht, ob ein Geraet wirklich an ist -- er merkt sich nur, was er selbst geschaltet hat. Geht ein
Fernseher von selbst aus (eigener Schlaf-Timer) oder nimmt jemand die Original-Fernbedienung, schaltet der naechste
Wechsel verkehrt herum. Home Assistant kennt den echten Zustand oft: ein media_player, eine Steckdose mit
Strommessung, ein binary_sensor.

Je Hub-Geraet (tv, soundbar, receiver, android, x0..x3) laesst sich in den Optionen eine Entitaet zuordnen. Die
Integration schickt "zustand:<g>:<0|1>[:n]" auf <base>/<id>/cmd:
- bei jeder Aenderung (an/aus) der Entitaet, wenn der Hub fragt ("*" = alle, nach jedem Verbinden) und wenn Home
  Assistant selbst wieder mit dem Broker verbunden ist;
- 'n' = Nachfassen erlaubt. Dann fragt der Hub 10 s nach dem eigenen Ein/Aus nach (<base>/<id>/zustand_frage =
  <g>:<Nummer>), die Integration holt den Zustand frisch (homeassistant.update_entity) und antwortet mit
  "...:nf<Nummer>" -- nur die Antwort mit der Nummer seiner Frage laesst der Hub nachfassen.
Was daraus folgt, entscheidet der Hub (Sperrzeit nach eigenem Schalten, hoechstens einmal nachfassen).
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    CONF_ENTITY,
    CONF_NACHFASSEN,
    CONF_SCHWELLE,
    CONF_ZUSTAND,
    DEFAULT_BASE_TOPIC,
    DEFAULT_SCHWELLE,
)

_LOGGER = logging.getLogger(__name__)

GERAETE = ("tv", "soundbar", "receiver", "android", "x0", "x1", "x2", "x3")
AUS = {"off", "standby"}
UNBEKANNT = {"unavailable", "unknown", ""}
# 0.14.1: die Schwelle ist in Watt. Ein Leistungs-Sensor in kW meldete 0,08 statt 80 und galt damit als "aus"
# (gegen 15 W verglichen). Unbekannte oder fehlende Einheit: wie bisher, der Zahlenwert gilt als Watt.
EINHEIT_IN_WATT = {"W": 1.0, "kW": 1000.0, "MW": 1_000_000.0, "mW": 0.001}


def an_aus(state: State | None, schwelle: float) -> bool | None:
    """An (True), aus (False) oder nicht zu sagen (None) -- dann meldet die Integration nichts."""
    if state is None or state.state in UNBEKANNT:
        return None
    domain = state.entity_id.split(".")[0]
    if domain == "sensor":
        try:
            wert = float(state.state)
            grenze = float(schwelle)
        except (TypeError, ValueError):
            return None
        faktor = EINHEIT_IN_WATT.get(state.attributes.get("unit_of_measurement") or "W", 1.0)
        return wert * faktor > grenze
    if domain == "media_player":
        return state.state not in AUS
    if state.state == "on":
        return True
    if state.state == "off":
        return False
    return None


def zuordnungen(entry: ConfigEntry) -> dict[str, dict]:
    """Die gueltigen Zuordnungen aus den Optionen: {geraet: {entity, nachfassen, schwelle}}."""
    roh = entry.options.get(CONF_ZUSTAND)
    out: dict[str, dict] = {}
    if not isinstance(roh, dict):
        return out
    for g, cfg in roh.items():
        if g in GERAETE and isinstance(cfg, dict) and isinstance(cfg.get(CONF_ENTITY), str) and cfg[CONF_ENTITY]:
            out[g] = cfg
    return out


class ZustandMelder:
    """Meldet die zugeordneten Zustaende an einen Hub und beantwortet seine Fragen."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.map = zuordnungen(entry)
        base = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
        device_id = entry.data[CONF_DEVICE_ID]
        self.cmd_topic = f"{base}/{device_id}/cmd"
        self.frage_topic = f"{base}/{device_id}/zustand_frage"

    async def async_start(self) -> None:
        """Abos anlegen und einmal alles melden. Ohne Zuordnung passiert nichts (keine Abos, keine Nachrichten)."""
        if not self.map:
            return
        entities = sorted({cfg[CONF_ENTITY] for cfg in self.map.values()})
        self.entry.async_on_unload(
            async_track_state_change_event(self.hass, entities, self._on_state)
        )
        self.entry.async_on_unload(
            await mqtt.async_subscribe(self.hass, self.frage_topic, self._on_frage)
        )
        # Nach einem Neustart des Brokers: der Hub fragt nach dem Verbinden ("*"), ist Home Assistant aber erst danach
        # wieder da, geht seine Frage verloren -- deshalb meldet die Integration auch selbst, sobald sie verbunden ist
        self.entry.async_on_unload(
            mqtt.async_subscribe_connection_status(self.hass, self._on_verbindung)
        )
        await self._alle_melden()

    @callback
    def _on_verbindung(self, verbunden: bool) -> None:
        if verbunden:
            self.hass.async_create_task(self._alle_melden())

    def _schwelle(self, cfg: dict) -> float:
        try:
            return float(cfg.get(CONF_SCHWELLE, DEFAULT_SCHWELLE))
        except (TypeError, ValueError):
            return float(DEFAULT_SCHWELLE)

    async def _melden(self, g: str, an: bool, nr: str = "") -> None:
        """nr = Nummer der Frage des Hubs (frische Antwort), sonst leer."""
        flags = ("n" if self.map[g].get(CONF_NACHFASSEN) else "") + (f"f{nr}" if nr else "")
        payload = f"zustand:{g}:{1 if an else 0}" + (f":{flags}" if flags else "")
        _LOGGER.debug("RealMote: %s -> %s", payload, self.cmd_topic)
        try:
            await mqtt.async_publish(self.hass, self.cmd_topic, payload)
        except HomeAssistantError as err:
            # Broker gerade weg: nicht die ganze Integration (und mit ihr die Smart-Home-Tasten) scheitern lassen --
            # nach dem Wiederverbinden fragt der Hub ohnehin alle Zustaende ab ("*")
            _LOGGER.warning("RealMote: Zustand %s nicht gesendet: %s", payload, err)

    async def _alle_melden(self) -> None:
        for g, cfg in self.map.items():
            an = an_aus(self.hass.states.get(cfg[CONF_ENTITY]), self._schwelle(cfg))
            if an is not None:
                await self._melden(g, an)

    @callback
    def _on_state(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        for g, cfg in self.map.items():
            if cfg[CONF_ENTITY] != entity_id:
                continue
            schwelle = self._schwelle(cfg)
            neu = an_aus(event.data["new_state"], schwelle)
            alt = an_aus(event.data["old_state"], schwelle)
            if neu is not None and neu != alt:
                self.hass.async_create_task(self._melden(g, neu))

    @callback
    def _on_frage(self, msg: mqtt.ReceiveMessage) -> None:
        self.hass.async_create_task(self._frage_beantworten(str(msg.payload).strip()))

    async def _frage_beantworten(self, frage: str) -> None:
        if frage == "*":
            await self._alle_melden()
            return
        g, _, nr = frage.partition(":")
        cfg = self.map.get(g)
        if not cfg or not cfg.get(CONF_NACHFASSEN) or not nr.isdigit() or len(nr) != 1:
            return   # Nachfassen ist fuer dieses Geraet nicht eingeschaltet (oder die Frage ist unverstaendlich)
        entity_id = cfg[CONF_ENTITY]
        try:
            async with asyncio.timeout(5):
                await self.hass.services.async_call(
                    "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
                )
        except Exception:  # noqa: BLE001 -- nicht jede Entitaet laesst sich abfragen; dann gilt der letzte Stand
            _LOGGER.debug("RealMote: %s liess sich nicht frisch abfragen", entity_id)
        await asyncio.sleep(2)
        an = an_aus(self.hass.states.get(entity_id), self._schwelle(cfg))
        if an is not None:
            await self._melden(g, an, nr)
