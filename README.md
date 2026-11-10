<p align="center">
  <img src="https://raw.githubusercontent.com/aTTaTT82/realmote-ha/main/images/remote.png" alt="RealMote" width="240">
</p>

<h1 align="center">RealMote – Home Assistant Integration</h1>

Macht aus dem **RealMote Hub** (Funk-Fernbedienung mit den sechs Smart-Home-Tasten I–VI + ESP32-Hub) ein echtes
Home-Assistant-Gerät: Du legst jede Smart-Home-Taste direkt im Geräte-Menü auf ein beliebiges HA-Gerät
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
3. Fertig. Tastendruck auf der Fernbedienung führt die Aktion aus. Bleibt **lang halten** frei, macht langes Halten
   dasselbe wie kurz tippen — es sei denn, im Hub steht für diese Taste ein eigenes Lang-Thema. Hub und Integration
   melden einander, wo lang belegt ist; bei langem Druck kommt nie lang **und** kurz (ab 0.14.3 mit Hub ab 4.81.79).

## Aktionen
| Aktion | Wirkt auf | Extra-Feld |
|---|---|---|
| Umschalten | Licht, Schalter, … | – |
| An / Aus | Licht, Schalter, … | Helligkeit % (Licht) |
| Öffnen / Schließen | Rollo/Cover | – |
| Position setzen | Rollo/Cover | Position % |

## 🗣️ Tasten aus HA ausführen (z. B. „Alexa, Pause")
Ab v0.8.0 (+ Hub-Firmware ≥ 4.13.0) gibt es am Gerät **drückbare Knöpfe für die
einzelnen Tasten**: „Pause senden", „Play senden", „Lautstärke + senden", … Ein
Druck wirkt **Activity-bewusst** wie ein Druck auf der Fernbedienung — „Pause"
pausiert also genau das Gerät, das gerade die Wiedergabe macht.

Standardmäßig sind die Medien-/Lautstärke-/Kanal-Tasten aktiv; selten gebrauchte
(Farben, Navigation, HDMI, …) sind als Entity vorhanden, aber deaktiviert —
einfach in HA bei Bedarf aktivieren.

Für Sprachsteuerung: den gewünschten Knopf (z. B. „Pause senden") wie gewohnt an
Alexa/Google durchreichen und eine Routine mit eigenem Sprachbefehl darauf legen.

Ab v0.13.0 gibt es dazu **„Ziffer 0 senden" … „Ziffer 9 senden"** (Hub ≥ 4.81.59) und
**„Quelle senden"** (Hub ≥ 4.81.49) — ebenfalls Activity-bewusst und von Haus aus
deaktiviert. Ein Sender per Nummer ist damit ein Skript aus zwei Knöpfen, z. B.
„Ziffer 1 senden" + „Ziffer 2 senden" für Programm 12.

## ⭐ Eigene Tasten je Gerät (z. B. „Fernseher: Netflix senden")
Ab v0.13.0 (+ Hub-Firmware ≥ 4.81.61): Jede **eigene Taste**, die du in der
Konfiguration des Hubs angelernt hast (bis zu 10 je Gerät, mit selbst gewähltem Namen),
erscheint am RealMote-Gerät als Knopf — benannt nach Gerät und Taste, z. B.
**„Fernseher: Netflix senden"** oder **„Beamer: Bildmodus senden"**.

Anders als die übrigen Tasten-Knöpfe geht ein Druck **direkt an dieses Gerät**, egal
welche Activity läuft — der Name gehört ja zu genau einem Gerät. Neue, umbenannte oder
gelöschte eigene Tasten übernimmt Home Assistant von selbst (der Hub meldet sie über
`realmote/<id>/tasten`); Knöpfe zu gelöschten Tasten verschwinden wieder.

## 🎚️ Laufende Aktivität sehen und wählen (v0.14.0)
Am RealMote-Gerät gibt es die Auswahl **„Aktivität“** (Aus und deine drei Aktivitäten). Sie zeigt, was
gerade läuft — egal ob an der Fernbedienung, in der Webremote, per Alexa oder in Home Assistant gewechselt —
und schaltet um, wenn du eine andere wählst. Damit reagieren Automationen auf den Wechsel, z. B. „Filmabend
startet → Licht dimmen“ (siehe **Rezepte** unten). Braucht Hub-Firmware ≥ 4.81.64.

## 🔋 Akku der Fernbedienung (v0.14.0)
Der Sensor **„Akku Fernbedienung“** (unter *Diagnose*) zeigt den Ladestand in Prozent. Der Hub übernimmt ihn
einmal am Tag aus den Funkpaketen; nach einem Neustart des Hubs kommt der Wert mit dem ersten Tastendruck.
Hängen mehrere Fernbedienungen an einem Hub, zeigt er den Wert, den der Hub zuletzt übernommen hat — von der
Fernbedienung, die nach dem Neustart bzw. nach Ablauf des Tages als erste gefunkt hat. Hub-Firmware ≥ 4.81.64.

## 🔌 Echter Zustand der Geräte (v0.14.0)
Der Hub merkt sich nur, was er selbst geschaltet hat. Geht der Fernseher von selbst aus (eigener Schlaf-Timer)
oder nimmt jemand die Original-Fernbedienung, schaltet der nächste Wechsel verkehrt herum — das klassische
Problem aller Universalfernbedienungen. Kennt Home Assistant den echten Zustand, übernimmt der Hub ihn:

1. Beim Gerät auf **Konfigurieren** → **„Zustand der Geräte aus Home Assistant“** → Gerät des Hubs wählen
   (Fernseher, Soundbar, Sat/Kabel, Android TV, weitere Geräte).
2. Die Entität wählen, die den Zustand kennt: am zuverlässigsten eine **Steckdose mit Strommessung**
   (Leistungs-Sensor, „an“ ab der Schwelle in Watt, Vorgabe 15 W; ein Sensor in kW wird seit 0.14.1 umgerechnet)
   oder der Mediaplayer des Geräts selbst.
   Ein Mediaplayer, der „nicht verfügbar“ zeigt, wenn das Gerät aus ist, hilft nicht.
3. Optional **Nachfassen**: 10 s nach dem Ein- oder Ausschalten fragt der Hub nach; stimmt der Zustand nicht,
   schickt er den Befehl einmal noch. Nur einschalten, wenn die Entität schnell und zuverlässig meldet.

Was der Hub daraus macht: weicht der gemeldete Zustand ab, gilt er (gesendet wird dabei nichts) — der nächste
Wechsel schaltet richtig herum, und ein **erneuter Druck auf die laufende Aktivität schaltet Geräte ein**, die
laut Home Assistant aus sind. Bis 30 s nach dem eigenen Schalten zählt eine widersprechende Meldung noch
nicht (Home Assistant sieht ein Gerät oft erst Sekunden später an) — die letzte aus dieser Zeit gilt, sobald
sie vorbei ist. Ohne Zuordnung ändert sich nichts. Hub-Firmware ≥ 4.81.64.

## 📋 Fertige Rezepte (Blueprints, v0.14.0)
Mit einem Klick importieren (öffnet dein Home Assistant), dann unter *Automatisierungen → Blueprints* eine
Automation daraus anlegen:

| Rezept | Was es tut | Importieren |
|---|---|---|
| Wenn eine Aktivität startet | Deine Aktionen, sobald eine bestimmte Aktivität startet (z. B. Licht dimmen, Rollos runter; „Aus“ = alles aus) | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FaTTaTT82%2Frealmote-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Frealmote%2Faktivitaet_startet.yaml) |
| Pause bei Anruf | Klingelt das Handy, pausiert der Hub die Wiedergabe; auf Wunsch weiter nach dem Gespräch (Telefonstatus der HA-App, nur Android) | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FaTTaTT82%2Frealmote-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Frealmote%2Fpause_bei_anruf.yaml) |
| Alles aus, wenn niemand zu Hause ist | Ist eine Weile niemand mehr in der Zone „Zuhause“, schaltet der Hub alles aus | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FaTTaTT82%2Frealmote-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Frealmote%2Fniemand_zuhause_alles_aus.yaml) |
| Akku der Fernbedienung niedrig | Meldet sich einmal, wenn der Akku unter die Schwelle fällt (nicht nach jedem HA-Neustart erneut) | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FaTTaTT82%2Frealmote-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Frealmote%2Fakku_niedrig.yaml) |

Die Dateien liegen unter [`blueprints/automation/realmote/`](blueprints/automation/realmote/).

## 🎛️ Jede Taste als HA-Ereignis (Automationen auf ALLE Tasten)
Ab v0.7.0 (+ Hub-Firmware ≥ 4.12.0) taucht **jede Taste der Fernbedienung** als
**Ereignis-Entity** am RealMote-Gerät auf (z. B. „Taste Rot", „Taste Play",
„Taste Kanal +", auch Activity- und Power-Tasten). Die Taste macht weiterhin ganz
normal ihre Fernbedienungs-Funktion — das Ereignis kommt **zusätzlich**.

Damit lassen sich beliebige Automationen bauen: *„Wenn Taste Blau gedrückt →
Staubsauger starten"*, *„Wenn Taste Aus gedrückt → auch alle Lichter aus"*, usw.
Trigger in HA: Automation → Auslöser → Entität → die gewünschte „Taste …"-Entity.
(Die Smart-Home-Tasten 1–6 behalten ihre eigenen 12 Aktions-Slots.)

## ▶️ Hub-Activities aus HA starten (z. B. „Android TV")
Ab v0.6.0 (+ Hub-Firmware ≥ 4.11.0) legt die Integration **Knopf-Entities** am
RealMote-Gerät an: je Activity ein Knopf (Namen kommen vom Hub, z. B. „TV gucken",
„Android TV", „Musik") plus **„Alles aus"**. Ein Druck startet die komplette
Activity auf dem Hub (TV an, HDMI-Eingang, Soundbar, Android-Wake, …).

Damit lässt sich der Gerätestart in Szenen-Abläufe einbauen — als **Skript**:

1. *Einstellungen → Automatisierungen & Szenen → Skripte → Skript hinzufügen*,
   z. B. „Filmabend": Aktion 1 = Szene „Licht Filmabend" aktivieren,
   Aktion 2 = Knopf „Android TV" drücken.
2. Das Skript in RealMote auf eine Taste legen (Skripte sind direkt wählbar).

Die Knöpfe funktionieren natürlich auch im Dashboard, in Automationen und per
Sprachassistent.

## 🎬 Ganze Szenen auf eine Taste legen
Im Feld **„Gerät / Szene / Skript"** kannst du auch eine **Szene** oder ein **Skript**
auswählen — so legst du eine ganze Stimmung (mehrere Lampen, Rollos, Mediaplayer, …)
auf eine einzige Taste:

1. Szene in HA zusammenstellen: **Einstellungen → Automatisierungen & Szenen → Szenen → Szene hinzufügen**
   (Geräte reinziehen, gewünschte Zustände einstellen, speichern).
2. In RealMote den Tasten-Slot öffnen und die Szene als Ziel wählen.

Die „Aktion" ist dabei egal — Szenen werden **immer aktiviert**, Skripte **immer gestartet**,
Button-Entities **immer gedrückt** (die Integration erkennt den Typ selbst, es kann nichts
falsch eingestellt werden). Tipp: kurz tippen = Szene „Film", lang halten = Szene „Alles hell".

## ⬆️ Firmware-Update aus Home Assistant (v0.9.0)
Der Hub erscheint jetzt unter **Einstellungen → Geräte & Dienste → Updates** wie jedes
andere Gerät: Version, Änderungsprotokoll, ein Knopf **Installieren**.

**Warum das nicht einfach der Hub selbst macht:** Beim Aufbau einer gesicherten Verbindung
blieben dem ESP32 damals (v0.9.0) nur rund **23 KB** freier Arbeitsspeicher; seit der Hub den
Speicher dafür aus dem PSRAM nimmt, ist es mehr. Aber jede
neue Funktion knabbert daran, und wenn es einmal nicht mehr reicht, könnte der Hub genau die
Reparatur nicht mehr laden, die das beheben würde. Deshalb übernimmt Home Assistant den
Internet-Teil: HA lädt Manifest und Firmware und **schiebt** die Datei über das lokale Netz
an den Hub.

**Sicher bleibt es trotzdem** — der Hub glaubt auch Home Assistant nicht:
1. Die Manifest-Angaben werden gegen die eingebettete Signatur geprüft (ECDSA gegen den fest
   in der Firmware verdrahteten Schlüssel).
2. Die Build-Nummer muss größer sein als die laufende (keine Rückstufung auf alte Versionen).
3. Das Abbild selbst wird gegen seine Signatur geprüft.

Ein manipuliertes Manifest beantwortet der Hub mit einer Ablehnung. Braucht Hub-Firmware
**≥ 4.19.1** (erst die meldet die Build-Nummer im Announce — ohne sie ließe sich innerhalb
einer Version nicht erkennen, dass ein Update bereitliegt).

## 🔋 Firmware der Fernbedienung aus Home Assistant (v0.10.0)
Neben der Hub-Firmware steht jetzt eine zweite Update-Entität: **„Aktualisierung
Fernbedienung"** (bis v0.10.0 „Firmware der Fernbedienung"). Sie zeigt, welche Version dort wirklich läuft, und welche veröffentlicht
ist — und kann sie ausliefern.

**Warum das vorher nicht ging:** Die Fernbedienung hängt nicht am Netz. Erreichbar ist sie
nur über den Hub und dessen Funkstrecke, und bis Hub 4.29 wusste niemand, welche Version
dort überhaupt läuft. Seit **Fernbedienung v3.9** meldet sie es von selbst — einmal je
Wachphase, in einem reservierten Funkpaket **unveränderter Größe** (eine neue Paketgröße
hätte alle Bestands-Fernbedienungen taub gemacht). Erst damit ist ein ehrliches
„Update verfügbar" möglich statt eines Dauerhinweises.

Arbeitsteilung wie bei der Hub-Firmware: HA holt das **signierte** Paket (`.rmf`) aus dem
Internet und schiebt es ins lokale Netz an den Hub. Der Hub prüft die Signatur **beim
Ablegen und noch einmal vor jedem Senden** — untergeschoben werden kann nichts.

> ⚠️ **Der letzte Schritt liegt nicht bei Home Assistant.** Nach dem Installieren muss an
> der Fernbedienung **eine beliebige Taste** gedrückt werden. Sie schläft bei 75 µA und ist
> für den Hub nicht anrufbar; sie horcht von sich aus nach, sobald sie benutzt wird. Die
> Versionsanzeige wechselt deshalb erst danach.

Braucht Hub-Firmware **≥ 4.29.0** (Endpunkt `/remotefwlatest`) und für die Versionsanzeige
Fernbedienung **≥ v3.9**. Fehlt eines von beidem, bleibt die Entität bewusst auf
„unbekannt", statt etwas zu behaupten.

## Hub-Einstellungen
Auf der **Geräteseite** in HA gibt es einen Link **„Gerät besuchen"** direkt zur
Weboberfläche des Hubs (Broker, WLAN, Firmware-Update). Die Firmware-Version wird ebenfalls
angezeigt und bei jedem Announce aktuell gehalten.

## Status
Die Version steht in `custom_components/realmote/manifest.json` und unter **Änderungen**.
Transport = MQTT. Firmware-Announce: `realmote/<id>/announce` (enthält `ip`, `fw`, `build`, `acts`),
Taster-Event: `realmote/<id>/button` = Tastennummer (lang gehalten: `/hold`), jede andere Taste: `/key`,
Befehle an den Hub: `realmote/<id>/cmd`. `realmote` ist das Basis-Topic des Hubs. Braucht Hub-Firmware **≥ 4.6.1**
für den Geräte-Link. Icon & Logo werden ab HA 2026.3 lokal aus dem `brand/`-Ordner geladen
(kein `home-assistant/brands`-Eintrag nötig).

### Änderungen
- **0.14.4** – 🏠 **Was schon im Hub belegt ist, steht jetzt in der Übersicht:** „im Hub belegt“, und wo eine Taste hier **und** im Hub belegt ist, die Warnung „auch im Hub belegt – beides läuft“; beim Belegen nennt das Formular denselben Hinweis. Der Hub meldet dafür ab 4.81.80 auch seine Kurz-Themen (`realmote/<id>/kurz_hub`, retained).
- **0.14.3** – ⏱️ **Nie lang und kurz zugleich:** Hub und Integration melden einander, wo „lang halten“ belegt ist
  (`realmote/<id>/lang_ha` und `…/lang_hub`, retained). Ist eine Taste irgendwo lang belegt, kommt bei langem Druck nur
  lang; nirgends belegt, wirkt lang wie kurz. 0.14.2 und Hub 4.81.78 schickten bei „kurz im Hub, lang hier“ beides.
  Braucht für den Rückfall auf kurz einen Hub ab 4.81.79 (ein älterer meldet seine Belegung nicht — dann bleibt ein
  freies „lang halten“ hier frei). Die Übersicht zeigt „wie kurz tippen“ bzw. „im Hub belegt“.
- **0.14.2** – ⏱️ **Lang halten ohne Belegung wirkt wie kurz tippen** (wie der Hub mit seinen eigenen Themen ab
  4.81.78). Bisher tat ein langer Druck auf so eine Taste nichts; die Übersicht zeigt das freie Feld als „wie kurz tippen“.
- **0.14.1** – 🔌 Zustand der Geräte: ein Leistungs-Sensor in **kW** (oder MW, mW) wird in Watt umgerechnet, bevor er mit
  der Schwelle verglichen wird. Bisher galten 0,08 kW als 0,08 W — das Gerät stand fälschlich auf „aus“.
- **0.14.0** – 🎚️ **Auswahl „Aktivität“** (zeigt und wechselt die laufende Aktivität), 🔋 **Sensor „Akku
  Fernbedienung“**, 🔌 **echter Zustand der Geräte aus Home Assistant** (Optionen: Gerät des Hubs →
  Entität, Nachfassen, Schwelle für Leistungs-Sensoren) und 📋 **vier Rezepte** (Blueprints): Aktivität
  startet, Pause bei Anruf, alles aus wenn niemand zu Hause, Akku niedrig. Braucht Hub-Firmware ≥ 4.81.64.
- **0.13.0** – ⭐ **Eigene Tasten je Gerät** als Knöpfe („Fernseher: Netflix senden"),
  direkt an dieses Gerät (`key:CUSTOM_k@<gerät>`), Liste und Namen live vom Hub
  (`realmote/<id>/tasten`, retained); Knöpfe zu gelöschten Tasten werden entfernt.
  Dazu **„Ziffer 0–9 senden"** und **„Quelle senden"** (Activity-bewusst, deaktiviert).
  Braucht Hub-Firmware ≥ 4.81.61 für die eigenen Tasten, ≥ 4.81.59 für die Ziffern.
  Robust gegen kaputte Nachrichten auf `tasten` (die übrigen Knöpfe bleiben), und eine
  Änderung, die schon beim Start von HA eintrifft, gilt sofort (Listener vor dem ersten Abo).
- **0.12.0** – 🎨 **Das echte RealMote-Logo** statt der gezeichneten Sechs-Tasten-Grafik.
  `brand/` und `images/` sind neu erzeugt; `logo.png` (heller Grund) trägt die Wortmarke
  in Graphit, `dark_logo.png` in Silber — das Blau bleibt in beiden, es trägt auf jedem
  Untergrund. Die Kachel bleibt in **beiden** Fassungen schwarz: ein erster Anlauf färbte
  sie mit um, dann stand ein dunkles R auf dunkelgrauem Grund.
  Erzeugt von `tools/make-marke.py --ha` im Hauptrepo — nicht von Hand nachziehen.
- **0.11.0** – ⬆️ Beide Firmware-Anzeigen stehen jetzt **ganz oben** auf der Geräteseite.
  Sie lagen unten, weil `UpdateEntity` sich in Home Assistant von Haus aus die Kategorie
  „Konfiguration" gibt und HA solche Entitäten in eine eigene Karte unter die
  Bedienelemente schiebt. Kategorie entfernt – und weil HA innerhalb einer Karte nur
  alphabetisch sortiert, heißen sie jetzt **„Aktualisierung Fernbedienung"** und
  **„Aktualisierung Hub"**. Das sortiert vor „Alles aus" und allen Tasten-Knöpfen.
  ⚠️ Wer sie umbenennt, schiebt sie wieder nach hinten – der Name *ist* die Sortierung.
- **0.10.0** – 🔋 **Firmware der Fernbedienung aus HA**: zweite Update-Entität mit
  Installieren-Knopf. Zeigt laufende gegen veröffentlichte Version (Fernbedienung meldet
  ihre Version ab v3.9) und liefert das signierte `.rmf` über den Hub per Funk aus.
  Der letzte Schritt bleibt ein Tastendruck an der Fernbedienung. Braucht Hub ≥ 4.29.0.
- **0.9.1** – Fix: Beim Start meldete die Firmware-Entität immer „Aktuell". Ursache: Sie
  fragte ab, bevor der MQTT-Announce mit der Hub-IP da war, und meldete dann die installierte
  Version als neueste. Jetzt wird die Abfrage nachgeholt, sobald der Announce eintrifft.
- **0.9.0** – ⬆️ **Firmware-Update direkt aus HA**: Update-Entity mit Installieren-Knopf.
  HA lädt die Firmware und schiebt sie an den Hub, weil dem Hub für den Download selbst
  nur ~23 KB Reserve bleiben. Signaturprüfung und Rückstufungs-Sperre bleiben beim Hub.
  Braucht Hub-Firmware ≥ 4.19.1.
- **0.8.0** – 🗣️ **Drückbare Tasten-Knöpfe** („Pause senden", …, Activity-bewusst) —
  für Alexa-/Google-Routinen, Dashboards, Skripte. Braucht Hub-Firmware ≥ 4.13.0
  (MQTT-Befehl `key:<NAME>`).
- **0.7.0** – 🎛️ **Jede Taste als Ereignis-Entity** (Farb-, Medien-, Navigations-,
  Activity- und Power-Tasten) für freie Automationen. Braucht Hub-Firmware ≥ 4.12.0.
- **0.6.0** – ▶️ **Activity-Knöpfe**: je Hub-Activity eine Button-Entity („TV gucken",
  „Android TV", „Musik", Namen live vom Hub) + „Alles aus" — für Skripte, Automationen,
  Dashboards. Braucht Hub-Firmware ≥ 4.11.0 (MQTT-Befehl `activity:N`).
- **0.5.0** – 🎬 **Szenen, Skripte & Button-Entities auf Tasten legen** — Typ wird automatisch
  erkannt (Szene → aktivieren, Skript → starten, Button → drücken), Aktions-Auswahl kann
  nichts mehr falsch machen; Hinweis-Texte im Zuweisen-Dialog.
- **0.4.0** – Tippen **und** Halten pro Taste → 12 Aktionen (Hub-Firmware ≥ 4.7.0).
- **0.3.1** – Kleinigkeiten & Doku.
- **0.3.0** – Eigenes Marken-Icon + Logo (`brand/`-Ordner).
- **0.2.3** – Tasten-Übersicht mit Gerätetyp-Emojis.
- **0.2.2** – README-Bild als PNG.
- **0.2.1** – Geräte-Link zur Hub-Weboberfläche, Remote-Grafik (3×2).
