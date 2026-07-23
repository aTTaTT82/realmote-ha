# RealMote – Home Assistant Integration

Macht aus dem **RealMote Hub** (6-Tasten-Funk-Fernbedienung + ESP32-Hub) ein echtes
Home-Assistant-Gerät: Du legst jede Taste direkt im Geräte-Menü auf ein beliebiges HA-Gerät
und eine Aktion – **inklusive Helligkeit für Lampen und Position für Rollos**. Keine
Automationen, keine Topics, kein YAML.

Der Hub meldet per MQTT nur „Taste N gedrückt" – *was* passiert, entscheidet diese Integration.

## Voraussetzungen
- Home Assistant mit eingerichteter **MQTT-Integration** (z. B. Mosquitto-Broker-App).
- Ein RealMote Hub mit Firmware **≥ 4.6.0**, verbunden mit demselben MQTT-Broker
  (im Hub unter `http://<hub-ip>/mqtt` konfiguriert).

## Installation (über HACS)
1. HACS → oben rechts ⋮ → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/aTTaTT82/realmote-ha`, Kategorie **Integration** → Hinzufügen.
3. „RealMote" installieren, dann **Home Assistant neu starten**.

## Einrichten
1. Wenn der Hub online ist, taucht er **automatisch** unter *Einstellungen → Geräte & Dienste*
   auf („Entdeckt"). Auf **Konfigurieren** → bestätigen.
   (Falls nicht: *Integration hinzufügen → RealMote* und die Geräte-ID von der `/health`-Seite eintragen.)
2. Beim Gerät auf **Konfigurieren** → Taste wählen → **Gerät** aus der Liste, **Aktion**
   (Umschalten/An/Aus/Öffnen/Schließen/Position), optional **Helligkeit %** oder **Position %**.
3. Fertig. Tastendruck auf der Fernbedienung führt die Aktion aus.

## Aktionen
| Aktion | Wirkt auf | Extra-Feld |
|---|---|---|
| Umschalten | Licht, Schalter, … | – |
| An / Aus | Licht, Schalter, … | Helligkeit % (Licht) |
| Öffnen / Schließen | Rollo/Cover | – |
| Position setzen | Rollo/Cover | Position % |

## Status
Prototyp (v0.1). Transport = MQTT. Firmware-Announce: `realmote/<id>/announce`,
Taster-Event: `realmote/<id>/button` = Tastennummer.
