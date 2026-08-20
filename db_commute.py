#!/usr/bin/env python3
"""
Pendelverbindungen Gaimersheim <-> München Hbf aus der DB Timetables API (v1).

Filtert auf Züge, deren Laufweg den Zielbahnhof enthält (also durchgehende
RB16-Fahrten ohne Umstieg), holt die Ankunftszeit am Zielbahnhof über die
Zugnummer dazu und mischt die Echtzeitdaten aus /fchg ein.

Zugangsdaten: DB_CLIENT_ID / DB_API_KEY als Umgebungsvariablen, sonst wird
--credentials <pfad-zur-json> gelesen.

Aufruf:
    python3 db_commute.py                       # beide Richtungen als JSON
    python3 db_commute.py --richtung hin        # nur Gaimersheim -> München
    python3 db_commute.py --richtung rueck      # nur München -> Gaimersheim
    python3 db_commute.py --ankunft-bis 09:45   # nur Züge, die rechtzeitig da sind
    python3 db_commute.py --check               # nur Zugangsdaten testen

Hinweis zur API: /plan liefert nur ein Fenster von rund 18 Stunden ab jetzt.
Stunden ausserhalb davon antworten mit HTTP 404 — das ist kein Fehler.
Rate limit laut Abo: 60 Anfragen pro Minute; ein voller Lauf braucht rund 20.
"""

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BASE = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
TZ = ZoneInfo("Europe/Berlin")

STATIONS = {
    "Gaimersheim": "8002171",
    "München Hbf": "8000261",
    "Ingolstadt Hbf": "8000183",
}

_HEADERS = None


def headers(cred_path=None):
    global _HEADERS
    if _HEADERS:
        return _HEADERS
    cid = os.environ.get("DB_CLIENT_ID")
    key = os.environ.get("DB_API_KEY")
    if (not cid or not key) and cred_path and os.path.exists(cred_path):
        data = json.load(open(cred_path))
        cid = cid or data.get("DB_CLIENT_ID")
        key = key or data.get("DB_API_KEY")
    if not cid or not key or cid.startswith("HIER_"):
        sys.exit("Keine gültigen Zugangsdaten (DB_CLIENT_ID / DB_API_KEY).")
    _HEADERS = {"DB-Client-Id": cid, "DB-Api-Key": key, "accept": "application/xml"}
    return _HEADERS


def get_xml(path, cred_path=None):
    """404 = ausserhalb des Planfensters, kein Fehler. 429 = einmal warten."""
    for attempt in range(2):
        r = requests.get(f"{BASE}{path}", headers=headers(cred_path), timeout=25)
        if r.status_code == 429:
            time.sleep(2)
            continue
        if r.status_code == 401:
            sys.exit("401 — Zugangsdaten abgelehnt. Client-ID und API-Key prüfen.")
        if r.status_code == 404 or not r.content.strip():
            return None
        r.raise_for_status()
        return ET.fromstring(r.content)
    return None


def parse_ts(raw):
    if not raw or len(raw) != 10:
        return None
    return datetime.strptime(raw, "%y%m%d%H%M").replace(tzinfo=TZ)


def plan_hours(eva, start, hours, cred_path):
    """Planfahrplan über mehrere Stunden einsammeln — parallel, aber gedrosselt.

    Sechs gleichzeitige Anfragen bleiben deutlich unter dem Limit von 60/Minute
    und drücken einen vollen Lauf von gut einer Minute auf rund 15 Sekunden.
    """
    times = [start + timedelta(hours=i) for i in range(hours)]

    def fetch(t):
        return get_xml(f"/plan/{eva}/{t.strftime('%y%m%d')}/{t.strftime('%H')}", cred_path)

    out = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for root in pool.map(fetch, times):
            if root is not None:
                out.extend(root.findall("s"))
    return out


def changes(eva, cred_path):
    """Echtzeitlage: je Zugnummer die Änderungen an Ab- und Ankunft."""
    root = get_xml(f"/fchg/{eva}", cred_path)
    by_num = {}
    if root is None:
        return by_num
    for s in root.findall("s"):
        tl = s.find("tl")
        num = tl.get("n") if tl is not None else None
        if not num:
            continue
        entry = by_num.setdefault(num, {})
        for tag in ("dp", "ar"):
            el = s.find(tag)
            if el is None:
                continue
            entry[tag] = {
                "ct": el.get("ct"),    # geänderte Zeit
                "cp": el.get("cp"),    # geändertes Gleis
                "cs": el.get("cs"),    # 'c' = entfällt
            }
    return by_num


def arrivals(eva, start, hours, cred_path):
    """Ankunftszeiten am Zielbahnhof, nach Zugnummer."""
    out = {}
    for s in plan_hours(eva, start, hours, cred_path):
        tl, ar = s.find("tl"), s.find("ar")
        if tl is None or ar is None:
            continue
        num = tl.get("n")
        if num and num not in out:
            out[num] = {"pt": ar.get("pt"), "pp": ar.get("pp")}
    return out


def collect(origin, dest, cred_path, window_hours=8, limit=6):
    now = datetime.now(TZ)
    eva_o, eva_d = STATIONS[origin], STATIONS[dest]

    stops = plan_hours(eva_o, now, window_hours, cred_path)
    chg_o = changes(eva_o, cred_path)
    # Ankünfte etwas weiter in die Zukunft, die Fahrt dauert ~75 Min
    arr_plan = arrivals(eva_d, now, window_hours + 3, cred_path)
    chg_d = changes(eva_d, cred_path)

    rows = []
    for s in stops:
        tl, dp = s.find("tl"), s.find("dp")
        if tl is None or dp is None:
            continue
        if dest not in (dp.get("ppth") or "").split("|"):
            continue

        planned = parse_ts(dp.get("pt"))
        if planned is None or planned < now - timedelta(minutes=2):
            continue

        num = tl.get("n")
        cd = chg_o.get(num, {}).get("dp", {})
        actual = parse_ts(cd.get("ct")) or planned
        delay = round((actual - planned).total_seconds() / 60)

        ap = arr_plan.get(num, {})
        arr_planned = parse_ts(ap.get("pt"))
        ca = chg_d.get(num, {}).get("ar", {})
        arr_actual = parse_ts(ca.get("ct")) or arr_planned
        arr_delay = (round((arr_actual - arr_planned).total_seconds() / 60)
                     if arr_planned and arr_actual else None)

        rows.append({
            "linie": dp.get("l") or f"{tl.get('c', '')}{num}",
            "zugnummer": num,
            "ab_plan": planned.strftime("%H:%M"),
            "ab_ist": actual.strftime("%H:%M"),
            "ab_verspaetung": delay,
            "ab_gleis": cd.get("cp") or dp.get("pp") or "—",
            "ab_gleis_geaendert": bool(cd.get("cp")),
            "an_plan": arr_planned.strftime("%H:%M") if arr_planned else None,
            "an_ist": arr_actual.strftime("%H:%M") if arr_actual else None,
            "an_verspaetung": arr_delay,
            "an_gleis": ca.get("cp") or ap.get("pp") or "—",
            "entfaellt": cd.get("cs") == "c" or ca.get("cs") == "c",
            "datum": planned.strftime("%d.%m."),
            "fahrzeit_min": (round((arr_planned - planned).total_seconds() / 60)
                             if arr_planned else None),
        })

    rows.sort(key=lambda r: (r["datum"], r["ab_plan"]))
    return rows[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--richtung", choices=["hin", "rueck", "beide"], default="beide")
    ap.add_argument("--fenster", type=int, default=8, help="Stunden ab jetzt (max ~18)")
    ap.add_argument("--ankunft-bis", help="HH:MM — nur Züge, die bis dahin ankommen")
    ap.add_argument("--credentials",
                    default="/mnt/user-data/uploads/workspace/dashboard/db-credentials.json")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.check:
        r = requests.get(f"{BASE}/station/BLS", headers=headers(args.credentials), timeout=20)
        print("OK — Zugangsdaten gültig." if r.status_code == 200
              else f"Fehlgeschlagen: HTTP {r.status_code}")
        return

    legs = []
    if args.richtung in ("hin", "beide"):
        legs.append(("Gaimersheim", "München Hbf"))
    if args.richtung in ("rueck", "beide"):
        legs.append(("München Hbf", "Gaimersheim"))

    result = {
        "abgerufen": datetime.now(TZ).strftime("%d.%m.%Y %H:%M"),
        "quelle": "DB Timetables API v1 (plan + fchg)",
        "hinweis": "Nur durchgehende Verbindungen ohne Umstieg.",
        "strecken": [],
    }
    for origin, dest in legs:
        rows = collect(origin, dest, args.credentials, args.fenster)
        if args.ankunft_bis:
            rows = [r for r in rows
                    if r["an_ist"] and r["an_ist"] <= args.ankunft_bis]
        result["strecken"].append({"von": origin, "nach": dest, "verbindungen": rows})

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
