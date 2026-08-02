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

WARUM-GANZ-OBEN (v0.11.0)
-------------------------
Beide Firmware-Entities standen bis v0.10.0 ganz unten auf der Geraeteseite.
Grund ist kein Zufall: `UpdateEntity` gibt sich per Vorgabe
`EntityCategory.CONFIG` (Home-Assistant-Quelltext, update/__init__.py) -- und
Konfigurations-Entities rendert HA in einer EIGENEN Karte, unterhalb der
Bedienelemente. Bei einem Geraet mit Activity-Knoepfen, Tasten-Knoepfen und
Ereignis-Entities fuer JEDE Taste liegt diese Karte sehr weit unten.

Zwei Hebel, mehr gibt HA nicht her:
  1. `_attr_entity_category = None` -> raus aus der Konfigurations-Karte,
     hinein in die oberste Karte (Bedienelemente).
  2. Innerhalb einer Karte sortiert HA **alphabetisch**; eine explizite
     Reihenfolge gibt es nicht. Deshalb heissen beide jetzt
     "Aktualisierung ..." -- das sortiert vor "Alles aus", "Android TV" und
     allem "... senden", und die beiden stehen direkt nebeneinander.

⚠️ Wer sie spaeter umbenennt, schiebt sie damit wieder nach hinten. Der Name
ist hier kein Geschmack, sondern die Sortierung.
⚠️ Nebenwirkung von (1): ohne Kategorie gelten sie als normale Entities und
tauchen dadurch auch in automatisch erzeugten Uebersichten auf. Das ist genau
das, was hier gewuenscht war (sichtbarer), aber es ist eine Aenderung.
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
    """Die Update-Entities anlegen: Hub-Firmware und Fernbedienungs-Firmware."""
    async_add_entities([RealMoteUpdate(hass, entry), RealMoteRemoteUpdate(hass, entry)])


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
    _attr_name = "Aktualisierung Hub"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    # Siehe WARUM-GANZ-OBEN oben in dieser Datei.
    _attr_entity_category = None
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
        """Neueste bekannte Version — oder None, wenn noch keine abgerufen wurde.

        ⚠️ KEIN Rueckfall auf die installierte Version! Genau das stand hier
        zuerst, und es war falsch: Beim Start fragt HA die Entity ab, BEVOR der
        (retained) MQTT-Announce mit der Hub-IP verarbeitet ist. Ohne IP bricht
        der Manifest-Abruf ab — mit Rueckfall meldete die Entity dann
        "installiert == neueste", also dauerhaft "Aktuell", ganz unabhaengig
        davon, ob ein Update bereitliegt. Ein Update-Hinweis, der nie erscheint,
        ist schlimmer als gar keiner.
        None laesst HA "unbekannt" anzeigen; sobald der Announce eintrifft,
        loest _updated() eine echte Abfrage aus (siehe async_added_to_hass).
        """
        return self._latest

    @property
    def release_summary(self) -> str | None:
        if not self._manifest:
            return None
        text = self._manifest.get("changelog") or ""
        return text[:255]                     # HA begrenzt die Zusammenfassung

    async def async_added_to_hass(self) -> None:
        """Auf neue Announces horchen (Version aendert sich nach dem Update).

        Der Announce bringt die Hub-IP — ohne sie ist kein Manifest-Abruf
        moeglich. Beim Start trifft er typischerweise NACH der ersten Abfrage
        ein, deshalb wird hier nachgeholt, solange noch kein Manifest vorliegt.
        """

        @callback
        def _updated(_data: dict) -> None:
            if self._manifest is None:
                # Erster Announce: jetzt ist die IP bekannt -> echte Abfrage
                self.async_schedule_update_ha_state(force_refresh=True)
            else:
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


class RealMoteRemoteUpdate(UpdateEntity):
    """Firmware der FERNBEDIENUNG — anzeigen und per Funk ausliefern.

    WARUM EINE ZWEITE ENTITY
    ------------------------
    Die Fernbedienung haengt nicht am Netz; erreichbar ist sie nur ueber den Hub
    und dessen Funkstrecke. Bis Hub 4.29.x wusste ausserdem niemand, welche
    Version dort ueberhaupt laeuft — seit Remote v3.9 meldet sie es (einmal je
    Wachphase, im Akku-Byte eines reservierten Pakets). Erst damit ist ein
    ehrliches "Update verfuegbar" moeglich statt eines Dauerhinweises.

    Arbeitsteilung wie bei der Hub-Firmware: HA holt das signierte Paket aus dem
    Internet und schiebt es ins lokale Netz an den Hub. Der Hub prueft die
    Signatur beim Ablegen UND noch einmal vor jedem Senden — HA kann nichts
    unterschieben.

    ⚠️ Der letzte Schritt liegt NICHT bei HA: nach dem Bereitstellen muss an der
    Fernbedienung eine beliebige Taste gedrueckt werden. Sie schlaeft bei 75 uA
    und ist fuer den Hub nicht anrufbar; sie horcht von sich aus nach, sobald
    sie benutzt wird. Deshalb meldet install() Erfolg, sobald das Paket
    scharfgestellt ist, und die Version wechselt erst spaeter.

    Voraussetzungen: Hub-Firmware >= 4.29.0 (Endpunkt /remotefwlatest),
    Fernbedienung >= v3.9 fuer die Versionsmeldung. Fehlt eines von beidem,
    bleibt die Entity bewusst auf "unbekannt", statt etwas zu behaupten.
    """

    _attr_has_entity_name = True
    _attr_name = "Aktualisierung Fernbedienung"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    # Siehe WARUM-GANZ-OBEN oben in dieser Datei.
    _attr_entity_category = None
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._device_id: str = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_remote_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=entry.data.get(CONF_NAME, self._device_id),
        )
        self._state: dict | None = None

    # ---------------------------------------------------------------- Zustand

    @property
    def _hub_ip(self) -> str | None:
        ann = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        return ann.get("ip") or self._entry.data.get(CONF_IP)

    @property
    def installed_version(self) -> str | None:
        """Was auf der Fernbedienung laeuft — None, solange sie nichts gemeldet hat.

        ⚠️ Kein Rueckfall auf die veroeffentlichte Version. Derselbe Fehler wie
        bei der Hub-Entity waere hier noch unangenehmer: die Anzeige stuende
        dauerhaft auf "aktuell", obwohl niemand weiss, was dort laeuft.
        """
        if not self._state:
            return None
        return self._state.get("running_version") if self._state.get("running_code") else None

    @property
    def latest_version(self) -> str | None:
        if not self._state or not self._state.get("published"):
            return None
        return self._state.get("latest_version")

    @property
    def available(self) -> bool:
        return self._state is not None

    @property
    def extra_state_attributes(self) -> dict | None:
        if not self._state:
            return None
        return {
            "hinweis": (
                "Nach dem Installieren eine beliebige Taste auf der Fernbedienung "
                "druecken — sie holt das Update dann selbst ab."
            ),
        }

    async def async_added_to_hass(self) -> None:
        """Der Announce bringt die Hub-IP; ohne sie ist keine Abfrage moeglich."""

        @callback
        def _updated(_data: dict) -> None:
            if self._state is None:
                self.async_schedule_update_ha_state(force_refresh=True)
            else:
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SIGNAL_ANNOUNCE}_{self._entry.entry_id}", _updated
            )
        )

    # ---------------------------------------------------------------- Abfrage

    async def async_update(self) -> None:
        """Den Hub fragen: was laeuft, was ist veroeffentlicht?

        Eine Abfrage genuegt — der Hub hat den Manifest-Block schon geprueft
        (inkl. Signatur) und kennt die laufende Version aus dem Funkverkehr.
        """
        ip = self._hub_ip
        if not ip:
            return
        try:
            session = async_get_clientsession(self.hass)
            async with asyncio.timeout(15):
                async with session.get(f"http://{ip}/remotefwlatest") as resp:
                    if resp.status == 404:
                        # Hub aelter als 4.29.0 — die Entity bleibt still.
                        return
                    resp.raise_for_status()
                    self._state = await resp.json(content_type=None)
        except Exception as err:  # noqa: BLE001 – Abruf darf die Entity nie killen
            _LOGGER.debug("RealMote: /remotefwlatest nicht abrufbar: %s", err)

    # ------------------------------------------------------------ Installieren

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:
        """Paket holen, an den Hub schieben, bereitstellen."""
        ip = self._hub_ip
        if not ip:
            raise HomeAssistantError("IP des Hubs unbekannt – Update nicht moeglich")
        if not self._state:
            await self.async_update()
        st = self._state
        if not st or not st.get("published"):
            raise HomeAssistantError(
                "Der Hub kennt keine veroeffentlichte Fernbedienungs-Firmware. "
                "Er sieht taeglich nach; erzwingen laesst es sich mit einem Aufruf "
                "von /updatecheck."
            )

        url = st.get("url")
        code = st.get("latest_code")
        if not url:
            raise HomeAssistantError("Im Manifest fehlt die Adresse des Pakets")

        session = async_get_clientsession(self.hass)
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            _LOGGER.info("RealMote: lade Fernbedienungs-Firmware %s", url)
            async with asyncio.timeout(DOWNLOAD_TIMEOUT):
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    payload = await resp.read()

            erwartet = int(st.get("size") or 0)
            if erwartet and len(payload) != erwartet:
                raise HomeAssistantError(
                    f"Heruntergeladenes Paket ist unvollstaendig "
                    f"({len(payload)} statt {erwartet} Bytes)"
                )

            # ?code= sagt dem Hub, WELCHE Version er ablegt. Ohne diese Angabe
            # weiss er es nicht und koennte spaeter nicht warnen, dass ein
            # veraltetes Paket bereitliegt — genau das ist am 02.08.2026
            # passiert und hat der Fernbedienung dieselbe Version ein zweites
            # Mal beschert.
            params = {"code": str(code)} if code else {}
            form = aiohttp.FormData()
            form.add_field("file", payload, filename="remote.rmf",
                           content_type="application/octet-stream")

            _LOGGER.info("RealMote: uebertrage %d Bytes an %s", len(payload), ip)
            async with asyncio.timeout(PUSH_TIMEOUT):
                async with session.post(
                    f"http://{ip}/remotefw", params=params, data=form
                ) as resp:
                    body = (await resp.text()).strip()
                    if resp.status != 200:
                        # Der Hub lehnt hier u. a. eine ungueltige Signatur ab.
                        raise HomeAssistantError(f"Hub hat abgelehnt ({resp.status}): {body}")

            # Scharfstellen. Erst danach holt die Fernbedienung es beim naechsten
            # Tastendruck ab — diesen letzten Schritt kann HA nicht ausloesen.
            async with asyncio.timeout(30):
                async with session.post(f"http://{ip}/remoteota") as resp:
                    body = (await resp.text()).strip()
                    if resp.status != 200:
                        raise HomeAssistantError(f"Bereitstellen fehlgeschlagen: {body}")

            _LOGGER.info(
                "RealMote: Fernbedienungs-Firmware bereitgestellt. "
                "Jetzt eine beliebige Taste an der Fernbedienung druecken."
            )
        finally:
            self._attr_in_progress = False
            self.async_write_ha_state()
