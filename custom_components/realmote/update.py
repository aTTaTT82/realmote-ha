"""Firmware-Update des Hubs — Home Assistant holt und schiebt.

WARUM DIESE PLATTFORM EXISTIERT
-------------------------------
Der Hub ist ein ESP32-S3 mit rund 23 KB freier Reserve, wenn eine gesicherte
Verbindung aufgebaut wird. Das reicht heute, aber jede neue Funktion knabbert
daran. Faellt die Reserve unter den Bedarf, kann der Hub sein Update nicht mehr
selbst laden — und weil genau dieser Kanal die Reparatur ausliefern wuerde, waere
ein ausgeliefertes Geraet dann verloren.

Loesung: Der Internet-Teil wird von dem Geraet erledigt, das ohnehin durchlaeuft
und weder Speicher- noch TLS-Sorgen hat — Home Assistant. HA holt Manifest und
Firmware und schiebt die Datei per HTTP ins lokale Netz an den Hub
(POST /updateupload, Hub-Firmware >= 4.19.0).

SICHERHEIT — unveraendert, der Hub glaubt niemandem:
  1. Die Manifest-Angaben werden gegen die eingebettete Signatur geprueft
     (ECDSA gegen den in der Firmware verdrahteten Public Key).
  2. Die Build-Nummer muss groesser sein als die laufende (Downgrade-Sperre).
  3. Das Abbild selbst wird gegen seine Signatur geprueft.
HA kann also nichts unterschieben; ein manipuliertes Manifest beantwortet der
Hub mit HTTP 403.

Voraussetzung fuer die Anzeige der richtigen Version: Hub-Firmware >= 4.19.1,
denn erst die meldet die Build-Nummer im Announce. Ohne sie liesse sich
innerhalb einer Version (4.19.0 Build 526..530) kein Update erkennen.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BUILD,
    CONF_DEVICE_ID,
    CONF_FW,
    CONF_IP,
    CONF_NAME,
    DOMAIN,
    SIGNAL_ANNOUNCE,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=6)      # Manifest hoechstens 4x taeglich abfragen
DOWNLOAD_TIMEOUT = 120                  # Firmware von GitHub holen
PUSH_TIMEOUT = 300                      # Uebertragung an den Hub (~15 s gemessen)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Die Update-Entity fuer diesen Hub anlegen."""
    async_add_entities([RealMoteUpdate(hass, entry)])


def _version_string(fw: str | None, build: int | None) -> str | None:
    """Anzeige- und Vergleichsversion: "4.19.0.531".

    Die Build-Nummer MUSS mit rein — innerhalb einer Version unterscheiden sich
    die Staende sonst nicht und HA wuerde faelschlich "aktuell" melden.
    """
    if not fw:
        return None
    return f"{fw}.{build}" if build else fw


class RealMoteUpdate(UpdateEntity):
    """Zeigt die Hub-Firmware an und installiert sie im Auftrag des Nutzers."""

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._device_id: str = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=entry.data.get(CONF_NAME, self._device_id),
        )
        self._manifest: dict | None = None
        self._latest: str | None = None

    # ---------------------------------------------------------------- Zustand

    @property
    def _announce(self) -> dict:
        return self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})

    @property
    def _hub_ip(self) -> str | None:
        return self._announce.get("ip") or self._entry.data.get(CONF_IP)

    @property
    def installed_version(self) -> str | None:
        ann = self._announce
        return _version_string(
            ann.get("fw") or self._entry.data.get(CONF_FW), ann.get(CONF_BUILD)
        )

    @property
    def latest_version(self) -> str | None:
        # Solange nichts abgerufen wurde, den installierten Stand melden —
        # sonst zeigt HA faelschlich ein Update an.
        return self._latest or self.installed_version

    @property
    def release_summary(self) -> str | None:
        if not self._manifest:
            return None
        text = self._manifest.get("changelog") or ""
        return text[:255]                     # HA begrenzt die Zusammenfassung

    async def async_added_to_hass(self) -> None:
        """Auf neue Announces horchen (Version aendert sich nach dem Update)."""

        @callback
        def _updated(_data: dict) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SIGNAL_ANNOUNCE}_{self._entry.entry_id}", _updated
            )
        )

    # ---------------------------------------------------------------- Abfrage

    async def _fetch_manifest_url(self) -> str:
        """Die im Hub hinterlegte Update-Quelle erfragen (dort auch aenderbar)."""
        ip = self._hub_ip
        if not ip:
            raise HomeAssistantError("IP des Hubs unbekannt (noch kein Announce empfangen)")
        session = async_get_clientsession(self.hass)
        async with asyncio.timeout(15):
            async with session.get(f"http://{ip}/updateurl") as resp:
                resp.raise_for_status()
                return (await resp.text()).strip()

    async def async_update(self) -> None:
        """Manifest holen und die neueste Version bestimmen."""
        try:
            url = await self._fetch_manifest_url()
            session = async_get_clientsession(self.hass)
            async with asyncio.timeout(30):
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    manifest = await resp.json(content_type=None)
        except Exception as err:  # noqa: BLE001 – Abruf darf die Entity nie killen
            _LOGGER.debug("RealMote: Manifest nicht abrufbar: %s", err)
            return

        self._manifest = manifest
        self._latest = _version_string(manifest.get("version"), manifest.get("build"))

    # ------------------------------------------------------------ Installieren

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:
        """Firmware holen und an den Hub schieben.

        HA uebernimmt hier bewusst den Internet-Teil; der Hub bekommt die fertige
        Datei ueber das lokale Netz und prueft die Signaturen selbst.
        """
        ip = self._hub_ip
        if not ip:
            raise HomeAssistantError("IP des Hubs unbekannt – Update nicht moeglich")
        if not self._manifest:
            await self.async_update()
        manifest = self._manifest
        if not manifest:
            raise HomeAssistantError("Update-Manifest nicht abrufbar")
        if not manifest.get("manifest_sig"):
            raise HomeAssistantError(
                "Das Manifest traegt keine Signatur – der Hub wuerde den Upload ablehnen. "
                "Es stammt vermutlich von einer aelteren Veroeffentlichung."
            )

        session = async_get_clientsession(self.hass)
        self._attr_in_progress = True
        self._attr_update_percentage = 0
        self.async_write_ha_state()
        try:
            # 1) Firmware ueber HA holen (voller TLS-Stack, kein Speicherproblem)
            _LOGGER.info("RealMote: lade Firmware %s", manifest.get("url"))
            async with asyncio.timeout(DOWNLOAD_TIMEOUT):
                async with session.get(manifest["url"]) as resp:
                    resp.raise_for_status()
                    payload = await resp.read()

            expected = int(manifest.get("size") or 0)
            if expected and len(payload) != expected:
                raise HomeAssistantError(
                    f"Heruntergeladene Firmware ist unvollstaendig "
                    f"({len(payload)} statt {expected} Bytes)"
                )
            self._attr_update_percentage = 50
            self.async_write_ha_state()

            # 2) An den Hub schieben. Die Manifest-Angaben gehen als Parameter mit,
            #    damit der Hub sie gegen die Signatur pruefen kann.
            params = {
                "version": str(manifest.get("version", "")),
                "build": str(manifest.get("build", 0)),
                "size": str(expected or len(payload)),
                "url": str(manifest.get("url", "")),
                "sig": str(manifest.get("sig", "")),
                "mansig": str(manifest.get("manifest_sig", "")),
            }
            form = aiohttp.FormData()
            form.add_field("fw", payload, filename="firmware.bin",
                           content_type="application/octet-stream")

            _LOGGER.info("RealMote: uebertrage %d Bytes an %s", len(payload), ip)
            async with asyncio.timeout(PUSH_TIMEOUT):
                async with session.post(
                    f"http://{ip}/updateupload", params=params, data=form
                ) as resp:
                    body = (await resp.text()).strip()
                    if resp.status != 200:
                        # 403 = Signatur/Downgrade abgelehnt -> Klartext weiterreichen
                        raise HomeAssistantError(f"Hub hat abgelehnt ({resp.status}): {body}")

            _LOGGER.info("RealMote: Update uebernommen, Hub startet neu (%s)", body)
            self._attr_update_percentage = 100
            self.async_write_ha_state()
            # Der Hub startet neu und meldet sich per Announce mit neuer Version.
            await asyncio.sleep(20)
        finally:
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()
