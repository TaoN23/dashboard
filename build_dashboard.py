#!/usr/bin/env python3
"""
Baut das Dashboard-HTML aus drei JSON-Dateien.

    python3 build_dashboard.py --termine termine.json \
                               --wetter wetter.json \
                               --zuege trains.json \
                               --out dashboard.html

Die Kalenderdaten kann kein Skript holen (das läuft über den MCP-Connector),
deshalb kommen sie als Datei herein. Zug- und Wetterdaten liefern
db_commute.py und wetter.py.

Jede Kachel trägt ihre Herkunftsstufe: live / fest / abgeleitet / beispiel.
"""

import argparse
import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
WOCHENTAG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
             "Freitag", "Samstag", "Sonntag"]
MONAT = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
         "August", "September", "Oktober", "November", "Dezember"]

CSS = """
:root{color-scheme:light;--plane:#f9f9f7;--surface-1:#fcfcfb;--text-primary:#0b0b0b;
--text-secondary:#52514e;--muted:#898781;--grid:#e1e0d9;--baseline:#c3c2b7;
--border:rgba(11,11,11,.10);--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--good:#0ca30c;
--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;--sample-wash:rgba(250,178,25,.07)}
/* Dunkle Werte unter BEIDEN Geltungsbereichen: die Media Query deckt die
   Systemeinstellung ab, der data-theme-Block den Umschalter der Oberfläche.
   Ohne den zweiten Block bleibt die Seite bei hellem System und dunklem
   Fenster auf hellen Tokens — dunkle Schrift auf dunklem Grund. */
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){color-scheme:dark;
--plane:#0d0d0d;--surface-1:#1a1a19;--text-primary:#fff;--text-secondary:#c3c2b7;
--muted:#898781;--grid:#2c2c2a;--baseline:#383835;--border:rgba(255,255,255,.10);
--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--sample-wash:rgba(250,178,25,.10)}}
:root[data-theme=dark],html[data-theme=dark],body[data-theme=dark],.dark,[data-mode=dark]{color-scheme:dark;
--plane:#0d0d0d;--surface-1:#1a1a19;--text-primary:#fff;--text-secondary:#c3c2b7;
--muted:#898781;--grid:#2c2c2a;--baseline:#383835;--border:rgba(255,255,255,.10);
--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--sample-wash:rgba(250,178,25,.10)}
*{box-sizing:border-box}
body{margin:0;padding:28px 20px 56px;background:var(--plane);color:var(--text-primary);
font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:15px;line-height:1.5;
-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.015em;font-weight:640}
.stand{color:var(--text-secondary);font-size:13.5px;margin:0}
.legend-prov{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--text-secondary);
border:1px solid var(--border);border-radius:999px;padding:3px 10px 3px 8px;background:var(--surface-1)}
.dot{width:8px;height:8px;border-radius:50%;flex:none;display:inline-block}
.dot.live{background:var(--good)}.dot.fixed{background:var(--series-1)}
.dot.sample{background:var(--warning)}.dot.derived{background:var(--muted)}
h2{font-size:12.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
font-weight:620;margin:34px 0 12px;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
h2 .tag{text-transform:none;letter-spacing:0;font-size:11.5px;padding:2px 8px;
border-radius:999px;font-weight:560;border:1px solid var(--border);color:var(--good)}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;padding:18px 20px}
.grid{display:grid;gap:12px}
.g-hero{grid-template-columns:1.45fr 1fr}.g-4{grid-template-columns:repeat(4,1fr)}
.g-3{grid-template-columns:repeat(3,1fr)}.g-5{grid-template-columns:repeat(5,1fr)}.g-2{grid-template-columns:repeat(2,1fr)}
@media (max-width:1000px){.g-5{grid-template-columns:repeat(3,1fr)}}
@media (max-width:820px){.g-hero,.g-4,.g-3,.g-2,.g-5{grid-template-columns:1fr}}
.kicker{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
font-weight:600;margin-bottom:7px;display:flex;align-items:center;gap:6px}
.hero-num{font-size:34px;font-weight:660;letter-spacing:-.02em;line-height:1.1;margin:0 0 2px}
.hero-sub{color:var(--text-secondary);font-size:14px;margin:0}
.val{font-size:26px;font-weight:640;letter-spacing:-.015em;line-height:1.15}
.unit{font-size:15px;font-weight:500;color:var(--text-secondary)}
.sub{color:var(--text-secondary);font-size:13px;margin-top:4px}
.note{color:var(--muted);font-size:12.5px;margin-top:8px}
.evrow{display:flex;align-items:baseline;gap:14px;padding:11px 0;border-top:1px solid var(--grid)}
.evrow:first-of-type{border-top:none;padding-top:2px}
.evwhen{flex:none;width:128px;color:var(--text-secondary);font-size:13px;font-variant-numeric:tabular-nums}
.evtitle{font-weight:560}.evmeta{color:var(--muted);font-size:12.5px}
.badge-in{flex:none;margin-left:auto;font-size:12px;color:var(--text-secondary);font-variant-numeric:tabular-nums}
.cd{display:flex;flex-direction:column;gap:2px}
.cd .days{font-size:30px;font-weight:660;letter-spacing:-.02em}
.cd .lbl{font-size:13px;font-weight:550}
.cd .date{color:var(--muted);font-size:12.5px;font-variant-numeric:tabular-nums}
.status{display:inline-flex;align-items:center;gap:7px;font-weight:580;font-size:15px}
.status.gruen{color:var(--good)}.status.gelb{color:var(--serious)}.status.rot{color:var(--critical)}
.sample{border-style:dashed;border-color:var(--warning);
background-image:repeating-linear-gradient(45deg,var(--sample-wash) 0 8px,transparent 8px 16px)}
.sample-badge{display:inline-flex;align-items:center;gap:6px;background:var(--warning);color:#0b0b0b;
font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:3px 9px;border-radius:5px}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:10px}
th{text-align:left;font-weight:600;color:var(--muted);font-size:11.5px;text-transform:uppercase;
letter-spacing:.05em;padding:0 10px 7px 0}
td{padding:8px 10px 8px 0;border-top:1px solid var(--grid);font-variant-numeric:tabular-nums}
td.name{font-variant-numeric:normal}
.ok{color:var(--good);font-weight:600}.warn{color:var(--serious);font-weight:600}
.bad{color:var(--critical);font-weight:600}
.legend{display:flex;gap:18px;margin:0 0 10px;font-size:12.5px;color:var(--text-secondary);flex-wrap:wrap}
.legend span{display:inline-flex;align-items:center;gap:7px}
.swatch{width:11px;height:11px;border-radius:3px;flex:none}
svg{display:block;width:100%;height:auto;overflow:visible}
.ax{fill:var(--muted);font-size:11px}.lab{fill:var(--text-secondary);font-size:11.5px}
.labstrong{fill:var(--text-primary);font-size:11.5px;font-weight:600}
.gridline{stroke:var(--grid);stroke-width:1}.baseline{stroke:var(--baseline);stroke-width:1}
footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--grid);
color:var(--text-secondary);font-size:13px}
footer h3{font-size:12.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
margin:0 0 8px;font-weight:620}
footer ul{margin:0 0 14px;padding-left:18px}footer li{margin-bottom:3px}
a{color:var(--series-1)}
.mailrow{padding:10px 0;border-top:1px solid var(--grid)}
.mailrow:first-of-type{border-top:none;padding-top:2px}
.mailwhen{color:var(--muted);font-size:11.5px;font-variant-numeric:tabular-nums;margin-bottom:2px}
.mailrow .evtitle{display:block;font-size:14.5px;line-height:1.35}
.mailrow .evmeta{display:block;margin-top:3px;line-height:1.4}
.daumen{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:6px;text-decoration:none;font-size:13.5px;
font-weight:560;padding:7px 13px;border-radius:9px;border:1px solid var(--border);
color:var(--text-primary);background:var(--plane);white-space:nowrap}
.btn:hover{border-color:var(--baseline)}
.btn.ja:hover{border-color:var(--good);color:var(--good)}
.btn.nein:hover{border-color:var(--critical);color:var(--critical)}
"""


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def stand_text(now):
    return (f"{WOCHENTAG[now.weekday()]}, {now.day}. {MONAT[now.month - 1]} "
            f"{now.year}, {now:%H:%M} Uhr (Europe/Berlin)")


# ---------------------------------------------------------------- Tracker 1
def block_termine(t):
    termine = t.get("termine", [])
    fristen = t.get("fristen", [])
    out = ['<h2>1 · Termine &amp; Fristen <span class="tag">● live aus Google Kalender</span></h2>']

    if termine:
        n = termine[0]
        wann = esc(n.get("wann", ""))
        extra = f'<p class="note">{esc(n["hinweis"])}</p>' if n.get("hinweis") else ""
        rest = "".join(
            f'<div class="evrow"><span class="evwhen">{esc(e.get("wann_kurz",""))}</span>'
            f'<span><span class="evtitle">{esc(e["titel"])}</span><br>'
            f'<span class="evmeta">{esc(e.get("ort") or "kein Ort hinterlegt")}</span></span>'
            f'<span class="badge-in">{esc(e.get("in_tagen",""))}</span></div>'
            for e in termine[1:4])
        if not rest:
            rest = ('<p class="note" style="margin-top:2px">Sonst steht in den nächsten '
                    'sechs Wochen nichts im Kalender.</p>')
        out.append(f"""
<div class="grid g-hero">
  <div class="card">
    <div class="kicker"><span class="dot live"></span>Nächster Termin</div>
    <p class="hero-num">{esc(n["titel"])}</p>
    <p class="hero-sub">{wann}</p>
    {extra}
  </div>
  <div class="card"><div class="kicker"><span class="dot live"></span>Danach</div>{rest}</div>
</div>""")
    else:
        out.append('<div class="card"><div class="kicker"><span class="dot live"></span>'
                   'Kalender</div><p class="hero-sub">In den nächsten sechs Wochen '
                   'steht nichts im Kalender.</p></div>')

    if fristen:
        tiles = "".join(
            f'<div class="card cd"><span class="days">{esc(f["tage"])}</span>'
            f'<span class="lbl">{esc(f["titel"])}</span>'
            f'<span class="date">{esc(f["datum"])}{esc(f.get("zusatz",""))}</span></div>'
            for f in fristen[:4])
        out.append(f'<div class="grid g-4" style="margin-top:12px">{tiles}</div>')

    out.append(zeitstrahl(termine, fristen))
    return "\n".join(out)


def zeitstrahl(termine, fristen):
    punkte = ([{"tage": e.get("tage"), "label": e["titel"], "art": "termin"}
               for e in termine if isinstance(e.get("tage"), int)] +
              [{"tage": f.get("tage"), "label": f["titel"], "art": "frist"}
               for f in fristen if isinstance(f.get("tage"), int)])
    punkte = [p for p in punkte if p["tage"] is not None and p["tage"] >= 0]
    if not punkte:
        return ""
    punkte.sort(key=lambda p: p["tage"])
    spanne = max(max(p["tage"] for p in punkte), 7)

    # Bewusst ohne Beschriftung an den Punkten: die Namen stehen schon in den
    # Kacheln und in der Terminliste darüber. Der Strahl zeigt hier nur, wie
    # sich die Termine über die Zeit verteilen — beschriftete Punkte kollidieren
    # bei Häufungen unweigerlich und machen die Grafik unlesbar.
    ACHSE_Y = 54

    def x_von(tage):
        return 60 + (tage / spanne) * 840

    marks = []
    for p in punkte[:12]:
        x = x_von(p["tage"])
        farbe = "var(--series-1)" if p["art"] == "termin" else "var(--series-2)"
        marks.append(
            f'<line class="baseline" x1="{x:.0f}" y1="{ACHSE_Y}" x2="{x:.0f}" y2="{ACHSE_Y-18}"/>'
            f'<circle cx="{x:.0f}" cy="{ACHSE_Y-22}" r="6" fill="{farbe}" '
            f'stroke="var(--surface-1)" stroke-width="2">'
            f'<title>{esc(p["label"])} — in {p["tage"]} Tagen</title></circle>')

    # Wochenraster als stille Orientierung
    raster = "".join(
        f'<line class="gridline" x1="{x_von(t):.0f}" y1="{ACHSE_Y}" '
        f'x2="{x_von(t):.0f}" y2="{ACHSE_Y+8}"/>'
        for t in range(7, spanne + 1, 7))

    return f"""
<div class="card" style="margin-top:12px">
  <div class="kicker"><span class="dot live"></span>Verteilung über die nächsten {spanne} Tage</div>
  <svg viewBox="0 0 1000 {ACHSE_Y + 34}" role="img" aria-label="Zeitstrahl: {len(punkte)} Termine und Fristen, verteilt über die nächsten {spanne} Tage. Die Namen stehen in den Kacheln darüber.">
    <line class="baseline" x1="60" y1="{ACHSE_Y}" x2="960" y2="{ACHSE_Y}"/>
    {raster}
    <circle cx="60" cy="{ACHSE_Y}" r="4" fill="var(--muted)"/>
    <text class="lab" x="60" y="{ACHSE_Y + 26}" text-anchor="middle">heute</text>
    <text class="lab" x="900" y="{ACHSE_Y + 26}" text-anchor="middle">in {spanne} Tagen</text>
    {''.join(marks)}
  </svg>
  <div class="legend" style="margin-top:6px">
    <span><span class="swatch" style="background:var(--series-1)"></span>Kalendertermin</span>
    <span><span class="swatch" style="background:var(--series-2)"></span>Feste Frist</span>
    <span style="color:var(--muted)">Raster: eine Woche · Namen in den Kacheln oben</span>
  </div>
</div>"""


# ---------------------------------------------------------------- Tracker 2
def block_wetter(w, now):
    orte = w.get("orte", [])
    if not orte:
        return ""
    # Ab dem späten Nachmittag ist der morgige Tag die interessantere Frage.
    abends = now.hour >= 16
    ampel = w.get("rad_ampel") or {}
    stufe = ampel.get("stufe", "unbekannt")
    ikone = {"grün": "✓", "gelb": "!", "rot": "✕"}.get(stufe, "?")
    css_stufe = {"grün": "gruen", "gelb": "gelb", "rot": "rot"}.get(stufe, "")

    def ort_kachel(o):
        if abends:
            f = o.get("morgen") or {}
            if f.get("nasse_stunden"):
                zeile = (f"{f['niederschlag_mm']} mm über {f['nasse_stunden']} h, "
                         f"ab etwa {esc(f['erste_nasse_stunde'])} Uhr")
            else:
                zeile = "trocken den ganzen Tag"
            return f"""
  <div class="card">
    <div class="kicker"><span class="dot live"></span>{esc(o['ort'])} morgen</div>
    <div class="val">{f.get('min','—')}<span class="unit"> bis </span>{f.get('max','—')}<span class="unit"> °C</span></div>
    <div class="sub">{zeile}</div>
  </div>"""
        j = o["jetzt"]
        return f"""
  <div class="card">
    <div class="kicker"><span class="dot live"></span>{esc(o['ort'])} jetzt</div>
    <div class="val">{j['temperatur']}<span class="unit"> °C</span></div>
    <div class="sub">{esc(j['zustand'])} · {j['bewoelkung_prozent']} % bewölkt ·
      Wind {j['wind_kmh']} km/h, Böen {j['boeen_kmh']} km/h</div>
  </div>"""

    stadt = next((o for o in orte if o["ort"] in ("München", "LMU", "Garching")), orte[-1])
    sonne = stadt["sonne_morgen"]
    kacheln = "".join(ort_kachel(o) for o in orte)
    # Sonnenzeiten und Rad-Ampel teilen sich eine Kachel — beides beantwortet
    # dieselbe Frage: komme ich mit dem Rad hin und im Hellen zurück?
    kacheln += f"""
  <div class="card">
    <div class="kicker"><span class="dot derived"></span>MVG-Rad-Ampel</div>
    <div class="status {css_stufe}"><span aria-hidden="true">{ikone}</span> {esc(stufe.capitalize())}</div>
    <div class="sub">{esc(ampel.get('grund',''))}</div>
    <div class="sub">Sonne in {esc(stadt['ort'])} morgen: {esc(sonne['aufgang'])} bis
      {esc(sonne['untergang'])} Uhr.</div>
    <p class="note">Aus den Wetterwerten abgeleitet, keine eigene Quelle.</p>
  </div>"""

    spalten = {2: "g-2", 3: "g-3", 4: "g-4"}.get(len(orte) + 1, "g-4")
    titel = "Wetter morgen" if abends else "Pendeln &amp; Wetter"
    return f"""
<h2>2 · {titel} <span class="tag">● live aus DWD-Daten</span></h2>
<div class="grid {spalten}">{kacheln}</div>
{temperatur_chart(orte, abends)}"""


def temperatur_chart(orte, abends):
    FARBEN = ["var(--series-1)", "var(--series-2)", "var(--series-3)"]
    fenster = ([("Morgen", "morgen"), ("Übermorgen früh", None)] if abends
               else [("Nächste 12 h", "naechste_12h"), ("Morgen", "morgen")])
    daten = []
    for label, key in fenster:
        if not key:
            continue
        for i, o in enumerate(orte):
            f = o.get(key)
            if f:
                daten.append((label, o["ort"], FARBEN[i % len(FARBEN)], f["min"], f["max"]))
    if not daten:
        return ""

    lo = min(d[3] for d in daten) - 2
    hi = max(d[4] for d in daten) + 2
    def x(v):
        return 118 + (v - lo) / (hi - lo) * 352

    zeilen, y, letzte_gruppe = [], 52, None
    for label, name, farbe, mn, mx in daten:
        if letzte_gruppe is not None and label != letzte_gruppe:
            y += 34
            zeilen.append(f'<text class="lab" x="0" y="{y-14}" font-weight="600">{esc(label)}</text>')
        elif letzte_gruppe is None:
            zeilen.append(f'<text class="lab" x="0" y="{y-22}" font-weight="600">{esc(label)}</text>')
        letzte_gruppe = label
        zeilen.append(
            f'<line x1="{x(mn):.0f}" y1="{y}" x2="{x(mx):.0f}" y2="{y}" stroke="{farbe}" stroke-width="2"/>'
            f'<circle cx="{x(mn):.0f}" cy="{y}" r="5.5" fill="{farbe}" stroke="var(--surface-1)" stroke-width="2"/>'
            f'<circle cx="{x(mx):.0f}" cy="{y}" r="5.5" fill="{farbe}" stroke="var(--surface-1)" stroke-width="2"/>'
            f'<text class="lab" x="{x(mn)-10:.0f}" y="{y+4}" text-anchor="end">{mn}°</text>'
            f'<text class="labstrong" x="{x(mx)+12:.0f}" y="{y+4}">{mx}° {esc(name)}</text>')
        y += 24

    ticks = []
    for i in range(4):
        v = lo + (hi - lo) * i / 3
        ticks.append(f'<line class="gridline" x1="{x(v):.0f}" y1="30" x2="{x(v):.0f}" y2="{y-10}"/>'
                     f'<text class="ax" x="{x(v):.0f}" y="{y+8}" text-anchor="middle">{v:.0f}°</text>')

    legende = "".join(
        f'<span><span class="swatch" style="background:{FARBEN[i % len(FARBEN)]}"></span>'
        f'{esc(o["ort"])}</span>' for i, o in enumerate(orte))
    return f"""
<div class="grid g-2" style="margin-top:12px">
  <div class="card">
    <div class="kicker"><span class="dot live"></span>Temperaturspannen</div>
    <div class="legend">{legende}</div>
    <svg viewBox="0 0 520 {y+24}" role="img" aria-label="Temperaturspannen je Zeitfenster und Ort in Grad Celsius; jede Spanne ist direkt beschriftet">
      {''.join(ticks)}{''.join(zeilen)}
    </svg>
  </div>
  <div class="card">
    <div class="kicker"><span class="dot live"></span>Niederschlag im Blick</div>
    {niederschlag_text(orte)}
  </div>
</div>"""


def niederschlag_text(orte):
    teile = []
    for o in orte:
        f = o.get("morgen")
        if not f:
            continue
        if f["nasse_stunden"]:
            teile.append(f'<p style="margin:6px 0 0"><strong>{esc(o["ort"])} morgen:</strong> '
                         f'{f["niederschlag_mm"]} mm über {f["nasse_stunden"]} Stunden, '
                         f'erste nasse Stunde gegen {esc(f["erste_nasse_stunde"])} Uhr. '
                         f'{f["min"]}–{f["max"]} °C.</p>')
        else:
            teile.append(f'<p style="margin:6px 0 0"><strong>{esc(o["ort"])} morgen:</strong> '
                         f'trocken, {f["min"]}–{f["max"]} °C.</p>')
    teile.append('<p class="note">Messwerte und Vorhersage des Deutschen Wetterdienstes, '
                 'stündlich aufgelöst. Niederschlag in Millimetern, nicht als '
                 'Wahrscheinlichkeit — „0 mm" heißt trocken.</p>')
    return "".join(teile)


# ---------------------------------------------------------------- Tracker 3
def block_zuege(z):
    if not z:
        return ""
    bloecke = []
    for s in z["strecken"]:
        rows = []
        for v in s["verbindungen"]:
            if v["entfaellt"]:
                status = '<span class="bad">✕ entfällt</span>'
            elif v["ab_verspaetung"] >= 6:
                status = f'<span class="bad">▲ +{v["ab_verspaetung"]} Min</span>'
            elif v["ab_verspaetung"] >= 1:
                status = f'<span class="warn">▲ +{v["ab_verspaetung"]} Min</span>'
            else:
                status = '<span class="ok">✓ pünktlich</span>'
            gleis = esc(v["ab_gleis"])
            if v["ab_gleis_geaendert"]:
                gleis = f'<span class="warn">{gleis} (neu)</span>'
            an = esc(v["an_plan"] or "—")
            if v.get("an_verspaetung"):
                an += f' <span class="warn">+{v["an_verspaetung"]}</span>'
            rows.append(
                f'<tr><td>{esc(v["datum"])} {esc(v["ab_plan"])}</td>'
                f'<td class="name">{esc(v["linie"])}</td><td>{gleis}</td>'
                f'<td>{an}</td>'
                f'<td>{v["fahrzeit_min"] or "—"} min</td><td>{status}</td></tr>')
        bloecke.append(f"""
  <div class="card">
    <div class="kicker"><span class="dot live"></span>{esc(s['von'])} → {esc(s['nach'])}</div>
    <table>
      <thead><tr><th>Ab</th><th>Linie</th><th>Gleis</th><th>An</th><th>Dauer</th><th>Status</th></tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="6">Keine durchgehende Verbindung im Zeitfenster.</td></tr>'}</tbody>
    </table>
  </div>""")

    return f"""
<h2>3 · Züge Gaimersheim ⇄ München <span class="tag">● live aus der DB Timetables API</span></h2>
<div class="grid g-2">{''.join(bloecke)}</div>
<p class="note" style="margin-left:2px">Nur durchgehende RB16-Verbindungen ohne Umstieg.
  Abgerufen {esc(z['abgerufen'])}. Der Planfahrplan reicht rund 18 Stunden in die Zukunft —
  weiter entfernte Fahrten liefert die API nicht.</p>"""


# ---------------------------------------------------------------- Für heute
def block_heute(tipp, musik):
    if not tipp and not musik:
        return ""
    teile = []

    if tipp:
        tags = "".join(f'<span class="chip">{esc(x)}</span>' for x in tipp.get("tags", []))
        teile.append(f"""
  <div class="card">
    <div class="kicker"><span class="dot derived"></span>Vorschlag für heute</div>
    <p class="hero-num" style="font-size:22px">{esc(tipp['titel'])}</p>
    <p style="margin:8px 0 0">{esc(tipp['text'])}</p>
    <p class="note">{esc(tipp.get('warum',''))}</p>
    <div class="legend-prov" style="margin-top:10px">{tags}</div>
  </div>""")

    if musik:
        bilanz = musik.get("bisher") or {}
        bilanz_text = ""
        if bilanz.get("ja") or bilanz.get("nein"):
            bilanz_text = (f'<p class="note">Bisher {bilanz.get("ja",0)}× Daumen hoch, '
                           f'{bilanz.get("nein",0)}× runter. '
                           f'{esc(musik.get("gelernt",""))}</p>')
        teile.append(f"""
  <div class="card">
    <div class="kicker"><span class="dot derived"></span>Musik für heute</div>
    <p class="val" style="font-size:20px">{esc(musik['track'])}</p>
    <div class="sub" style="font-size:14px">{esc(musik['artist'])}</div>
    <p style="margin:10px 0 0;font-size:14px">{esc(musik['warum'])}</p>
    <div class="daumen">
      <a class="btn" href="{esc(musik['spotify_url'])}" target="_blank" rel="noopener">▶ Auf Spotify</a>
      <a class="btn ja" href="{esc(musik['mailto_ja'])}">👍 Mehr davon</a>
      <a class="btn nein" href="{esc(musik['mailto_nein'])}">👎 Nicht mein Ding</a>
    </div>
    <p class="note">Die Daumen öffnen eine vorausgefüllte Mail an dich selbst — abschicken
      genügt, den Rest liest der nächste Lauf aus. Ein Herz in Spotify zählt genauso.</p>
    {bilanz_text}
  </div>""")

    return f'<h2>4 · Für heute <span class="tag" style="color:var(--muted)">◐ von mir vorgeschlagen</span></h2>\n<div class="grid g-2">{"".join(teile)}</div>'


# ---------------------------------------------------------------- Posteingang
def block_mails(m):
    if not m:
        return ""

    def liste(eintraege, leer):
        if not eintraege:
            return f'<p class="note" style="margin-top:2px">{leer}</p>'
        # Gestapelt statt zweispaltig: in einer Drittel-Kachel bliebe für den
        # Betreff sonst eine 4-Zeichen-Spalte übrig.
        return "".join(
            f'<div class="mailrow"><div class="mailwhen">{esc(e.get("wann",""))}</div>'
            f'<div class="evtitle">{esc(e["betreff"])}</div>'
            f'<div class="evmeta">{esc(e.get("absender",""))}'
            f'{" · " + esc(e["warum"]) if e.get("warum") else ""}</div></div>'
            for e in eintraege)

    aktion = m.get("aktion", [])
    persoenlich = m.get("persoenlich", [])
    rauschen = m.get("rauschen") or {}
    absender = rauschen.get("top_absender") or []

    aktion_karte = f"""
  <div class="card"{' style="border-color:var(--serious)"' if aktion else ''}>
    <div class="kicker"><span class="dot live"></span>Braucht etwas von dir</div>
    {liste(aktion, "Nichts offen.")}
  </div>"""

    stand = m.get("abgerufen")
    stand_tag = (f'<span class="tag" style="color:var(--muted)">zuletzt gelesen {esc(stand)}</span>'
                 if stand else "")
    return f"""
<h2>5 · Posteingang <span class="tag">● live aus Gmail</span> {stand_tag}</h2>
<div class="grid g-3">
  {aktion_karte}
  <div class="card">
    <div class="kicker"><span class="dot live"></span>Von Menschen und Institutionen</div>
    {liste(persoenlich, "Nichts Persönliches seit dem letzten Blick.")}
  </div>
  <div class="card">
    <div class="kicker"><span class="dot live"></span>Rauschen</div>
    <div class="val">{rauschen.get('anzahl', 0)}<span class="unit"> Newsletter &amp; Werbung</span></div>
    <div class="sub">{esc(", ".join(absender[:4])) if absender else "—"}</div>
    <p class="note">Nicht einzeln aufgelistet — das ist der Sinn der Kachel.
      Wenn dich einer davon nie interessiert, sag Bescheid, dann fliegt er raus.</p>
  </div>
</div>"""


# ---------------------------------------------------------------- Nachrichten
def block_news(n):
    if not n:
        return ""
    if not n.get("gefunden"):
        return f"""
<h2>6 · Nachrichten <span class="tag" style="color:var(--serious)">◌ Newsletter fehlt</span></h2>
<div class="card">
  <p style="margin:0">{esc(n.get('hinweis', 'Der Newsletter „Was jetzt?" lag heute früh nicht im Postfach.'))}</p>
  <p class="note">Hier steht bewusst nichts Erfundenes. Sobald die Mail da ist,
    füllt sich diese Kachel beim nächsten Lauf von selbst.</p>
</div>"""

    punkte = "".join(
        f'<div class="evrow" style="display:block"><span class="evtitle">{esc(p["titel"])}</span>'
        f'<p style="margin:4px 0 0;font-size:14px;color:var(--text-secondary)">{esc(p["text"])}</p></div>'
        for p in n.get("punkte", []))
    return f"""
<h2>6 · Nachrichten <span class="tag">● aus „Was jetzt?" von heute früh</span></h2>
<div class="card">
  {punkte}
  <p class="note">Zusammengefasst aus {esc(n.get('quelle', 'dem ZEIT-Newsletter'))}.
    Keine eigene Recherche — wenn der Newsletter etwas auslässt, fehlt es hier auch.</p>
</div>"""


# ---------------------------------------------------------------- Seite
def bauen(t, w, z, now, hat_beispieldaten=False,
          tipp=None, musik=None, mails=None, news=None):
    beispiel_chip = ('<span class="chip"><span class="dot sample"></span>'
                     'Beispieldaten — erfunden</span>') if hat_beispieldaten else ""
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Emilians Dashboard</title><style>{CSS}</style></head><body><div class="wrap">
<header>
  <h1>Emilians Dashboard</h1>
  <p class="stand">Stand: {stand_text(now)} · aktualisiert sich täglich um 06:30, 11:30, 16:30 und 20:30 Uhr</p>
  <div class="legend-prov">
    <span class="chip"><span class="dot live"></span>Live — bei jeder Aktualisierung neu abgerufen</span>
    <span class="chip"><span class="dot fixed"></span>Fest — verifiziertes oder genanntes Datum</span>
    <span class="chip"><span class="dot derived"></span>Abgeleitet — aus Live-Daten berechnet</span>
    {beispiel_chip}
  </div>
</header>
{block_termine(t)}
{block_wetter(w, now)}
{block_zuege(z)}
{block_heute(tipp, musik)}
{block_mails(mails)}
{block_news(news)}
<footer>
  <h3>Datenquellen</h3>
  <ul>
    <li><span class="dot live"></span> <strong>Termine</strong> — Google Kalender und Feiertagskalender Deutschland.</li>
    <li><span class="dot live"></span> <strong>Wetter</strong> — Deutscher Wetterdienst über Bright Sky. Sonnenzeiten lokal gerechnet.</li>
    <li><span class="dot live"></span> <strong>Züge</strong> — DB Timetables API v1 (plan + fchg), eigenes Abo.</li>
    <li><span class="dot fixed"></span> <strong>Semestertermine</strong> — geprüft auf lmu.de. <strong>HiWi-Start</strong> — von dir genannt.</li>
    <li><span class="dot live"></span> <strong>Posteingang</strong> — Gmail, sortiert nach Aktion / Persönlich / Rauschen.</li>
    <li><span class="dot live"></span> <strong>Nachrichten</strong> — zusammengefasst aus dem ZEIT-Newsletter „Was jetzt?", der morgens im Postfach liegt.</li>
    <li><span class="dot derived"></span> <strong>Rad-Ampel</strong> — aus den Wetterwerten berechnet.</li>
    <li><span class="dot derived"></span> <strong>Tagesvorschlag und Musik</strong> — von mir vorgeschlagen, auf Basis von Kalender, Wetter, deiner Spotify-Historie und deinem bisherigen Daumen-Feedback.</li>
  </ul>
  <h3>Wie es sich aktuell hält</h3>
  <p style="margin:0">Eine geplante Aufgabe baut diese Seite viermal täglich neu — 06:30,
    11:30, 16:30 und 20:30 Uhr. Ab dem Nachmittagslauf zeigt der Wetterblock den
    morgigen Tag statt den Rest von heute. Die Orte kommen aus deinem Kalender:
    was an dem Tag ansteht, bestimmt, für welche Orte das Wetter geholt wird.
    Ein zweiter Wächter prüft stündlich die Zuglage — aber nur, wenn ein Termin in
    München im Kalender steht; sonst bleibt er still.</p>
</footer>
</div></body></html>"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--termine", required=True)
    p.add_argument("--wetter", required=True)
    p.add_argument("--zuege")
    p.add_argument("--tipp", help="Tagesvorschlag als JSON")
    p.add_argument("--musik", help="Musikvorschlag als JSON")
    p.add_argument("--mails", help="Posteingang als JSON")
    p.add_argument("--news", help="Nachrichten als JSON")
    p.add_argument("--out", default="dashboard.html")
    a = p.parse_args()

    def lade(pfad):
        return json.load(open(pfad)) if pfad else None

    seite = bauen(lade(a.termine), lade(a.wetter), lade(a.zuege), datetime.now(TZ),
                  tipp=lade(a.tipp), musik=lade(a.musik),
                  mails=lade(a.mails), news=lade(a.news))
    open(a.out, "w").write(seite)
    print(f"geschrieben: {a.out}")


if __name__ == "__main__":
    main()
