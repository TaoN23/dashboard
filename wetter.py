#!/usr/bin/env python3
"""
Wetter für die Pendelstrecke aus DWD-Daten über die Bright-Sky-API.

Bright Sky (api.brightsky.dev) serviert die offenen Messwerte und Vorhersagen
des Deutschen Wetterdienstes: metrisch, stündlich, Niederschlag in mm, kein
API-Schlüssel nötig. Für Deutschland deutlich belastbarer als eine allgemeine
Wissensmaschine — die Stationen stehen im Land, nicht auf einem Flughafen in
der Nähe.

Sonnenauf- und -untergang werden lokal nach dem NOAA-Verfahren gerechnet,
damit dafür keine zweite Quelle nötig ist.

Aufruf:
    python3 wetter.py            -> JSON auf stdout
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from astral import LocationInfo
from astral.sun import sun

TZ = ZoneInfo("Europe/Berlin")
BASE = "https://api.brightsky.dev"

# Kleines Ortsverzeichnis für die Orte, an denen Emilian tatsächlich ist.
# Andere Orte lassen sich als "Name:lat,lon" mitgeben.
GAZETTEER = {
    "Wettstetten": (48.8206, 11.4128),      # Wohnort
    "Gaimersheim": (48.8006, 11.3628),      # Bahnhof, Klavierunterricht
    "Ingolstadt": (48.7665, 11.4258),
    "München": (48.1402, 11.5600),          # Hbf / Innenstadt
    "LMU": (48.1489, 11.5800),              # Schellingstr. / Theresienstr.
    "Garching": (48.2650, 11.6710),         # Forschungszentrum
}
STANDARD_ORTE = ["Wettstetten", "München"]

# Bright-Sky-Zustände auf deutsche Klartextlabels
CONDITION = {
    "dry": "trocken",
    "fog": "Nebel",
    "rain": "Regen",
    "sleet": "Schneeregen",
    "snow": "Schnee",
    "hail": "Hagel",
    "thunderstorm": "Gewitter",
    "null": "unbekannt",
}


def sonnenzeiten(lat, lon, tag):
    """Sonnenauf- und -untergang, lokale Zeit. Gegen Wolfram|Alpha geprüft."""
    ort = LocationInfo("", "DE", "Europe/Berlin", lat, lon)
    s = sun(ort.observer, date=tag, tzinfo=TZ)
    return s["sunrise"], s["sunset"]


def hole(ort, lat, lon):
    jetzt = datetime.now(TZ)
    aktuell = requests.get(f"{BASE}/current_weather",
                           params={"lat": lat, "lon": lon}, timeout=20).json()["weather"]
    stunden = requests.get(f"{BASE}/weather", params={
        "lat": lat, "lon": lon,
        "date": jetzt.strftime("%Y-%m-%d"),
        "last_date": (jetzt + timedelta(days=2)).strftime("%Y-%m-%d"),
        "tz": "Europe/Berlin",
    }, timeout=20).json()["weather"]

    def als_zeit(h):
        return datetime.fromisoformat(h["timestamp"]).astimezone(TZ)

    def spanne(von, bis):
        """Kennzahlen über ein Zeitfenster — nur was noch kommt, nicht der ganze Tag."""
        werte = [h for h in stunden
                 if von <= als_zeit(h) < bis and h.get("temperature") is not None]
        if not werte:
            return None
        temps = [h["temperature"] for h in werte]
        nass = [h for h in werte if (h.get("precipitation") or 0) > 0.1]
        return {
            "von": von.strftime("%d.%m. %H:%M"),
            "bis": bis.strftime("%d.%m. %H:%M"),
            "min": round(min(temps), 1),
            "max": round(max(temps), 1),
            "niederschlag_mm": round(sum(h.get("precipitation") or 0 for h in werte), 1),
            "nasse_stunden": len(nass),
            "erste_nasse_stunde": als_zeit(nass[0]).strftime("%H:%M") if nass else None,
            "stunden_erfasst": len(werte),
        }

    naechster_tag = (jetzt + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    auf, unter = sonnenzeiten(lat, lon, naechster_tag.date())

    return {
        "ort": ort,
        "jetzt": {
            "temperatur": aktuell.get("temperature"),
            "zustand": CONDITION.get(str(aktuell.get("condition")), aktuell.get("condition")),
            "bewoelkung_prozent": aktuell.get("cloud_cover"),
            "luftfeuchte_prozent": aktuell.get("relative_humidity"),
            "wind_kmh": aktuell.get("wind_speed_60"),
            "boeen_kmh": aktuell.get("wind_gust_speed_60"),
            "niederschlag_letzte_stunde_mm": aktuell.get("precipitation_60"),
            "messzeit": aktuell.get("timestamp"),
        },
        # Rollierendes Fenster ab jetzt — für einen Pendeltag interessanter
        # als der Kalendertag, der zur Hälfte schon vorbei ist.
        "naechste_12h": spanne(jetzt, jetzt + timedelta(hours=12)),
        "morgen": spanne(naechster_tag, naechster_tag + timedelta(days=1)),
        "sonne_morgen": {
            "aufgang": auf.strftime("%H:%M"),
            "untergang": unter.strftime("%H:%M"),
        },
    }


def orte_aufloesen(argument):
    """"Wettstetten,München" oder "Eichstätt:48.89,11.18" -> [(Name, lat, lon)]."""
    if not argument:
        argument = ",".join(STANDARD_ORTE)
    ergebnis = []
    for teil in [t.strip() for t in argument.split(",") if t.strip()]:
        if ":" in teil:                      # eigener Ort mit Koordinaten
            name, koord = teil.split(":", 1)
            lat, lon = (float(x) for x in koord.split(";"))
            ergebnis.append((name.strip(), lat, lon))
        elif teil in GAZETTEER:
            ergebnis.append((teil, *GAZETTEER[teil]))
        else:
            treffer = next((k for k in GAZETTEER if k.lower() == teil.lower()), None)
            if not treffer:
                sys.exit(f"Unbekannter Ort: {teil!r}. Bekannt: {', '.join(GAZETTEER)}. "
                         f"Eigene Orte als 'Name:lat;lon' angeben.")
            ergebnis.append((treffer, *GAZETTEER[treffer]))
    # Mehr als drei Orte werden im Dashboard unübersichtlich
    return ergebnis[:3]


def rad_ampel(muenchen):
    """Ampel für die MVG-Rad-Fahrt Hbf -> LMU. Rein abgeleitet.

    Ab dem späten Nachmittag zählt der morgige Tag, nicht der Rest von heute —
    abends interessiert die Frage „nehme ich morgen das Rad?", nicht „jetzt".
    """
    abends = datetime.now(TZ).hour >= 16
    jetzt = muenchen["jetzt"]
    fenster = (muenchen["morgen"] if abends else muenchen["naechste_12h"]) or {}
    t = fenster.get("max") if abends else jetzt.get("temperatur")
    regen = fenster.get("niederschlag_mm", 0) or 0
    boeen = jetzt.get("boeen_kmh") or 0

    bezug = "morgen" if abends else "in den nächsten 12 Stunden"
    if t is None:
        return {"stufe": "unbekannt", "grund": "keine Temperatur in den Daten", "bezug": bezug}
    if t < 0 or regen > 8 or boeen > 60:
        return {"stufe": "rot", "bezug": bezug,
                "grund": f"{regen} mm Regen {bezug} — das ist eine Bahn-und-Tram-Strecke"}
    if t < 5 or regen > 2 or boeen > 40:
        return {"stufe": "gelb", "bezug": bezug,
                "grund": f"{regen} mm {bezug}, {t} °C — Regenjacke oder lieber nicht"}
    return {"stufe": "grün", "bezug": bezug, "grund": f"trocken und mild {bezug}"}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--orte", help="Kommaliste, z.B. 'Wettstetten,München'. "
                                  "Eigene Orte als 'Name:lat;lon'. Maximal drei.")
    args = p.parse_args()

    orte = orte_aufloesen(args.orte)
    daten = {
        "abgerufen": datetime.now(TZ).strftime("%d.%m.%Y %H:%M"),
        "quelle": "Deutscher Wetterdienst über Bright Sky (api.brightsky.dev)",
        "orte": [hole(name, lat, lon) for name, lat, lon in orte],
    }
    # Die Rad-Ampel gilt der Fahrt Hbf -> LMU, hängt also an München.
    stadt = next((o for o in daten["orte"] if o["ort"] in ("München", "LMU", "Garching")), None)
    if stadt:
        daten["rad_ampel"] = rad_ampel(stadt)
    print(json.dumps(daten, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
