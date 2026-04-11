---
status: proposal
created: 2026-04-11
updated: 2026-04-11
scope: temperature-reliability, nav-rename, video-metadata, seasonal-video-selection, photo-curator
---

# Feature-Plan: Temperatur-Reliability, Dahoam, Video-Metadaten

Dieses Dokument bündelt vier lose gekoppelte Arbeitspakete. Jedes ist eigenständig
umsetzbar und per Commit/Deploy unabhängig veröffentlichbar.

## 1. Wassertemperatur zuverlässig aktualisieren

### Ist-Stand

- Quelle: Scraping von `gkd.bayern.de/.../muenchen-16005701/messwerte/tabelle`
  in [pipeline/fetch_and_store_isar.py:105-197](pipeline/fetch_and_store_isar.py#L105-L197)
- Cron: `0 */3 * * *` (alle 3h), siehe [Dockerfile.pipeline](Dockerfile.pipeline)
- Speicherung: tägliche JSONL-Dateien unter `data/current/water_temperature_YYYY-MM-DD.jsonl`
- Frontend liest die letzte Zeile der heutigen Datei in
  [web/src/lib/liveData.ts](web/src/lib/liveData.ts)
- Die letzten zwei Commits (`Handle missing temperature data gracefully`,
  `Find first valid temperature measurement in table`) haben Symptome behoben,
  aber noch keine strukturelle Reliability.

### Probleme, die wir adressieren

1. **Stille Stagnation**: wenn GKD mehrere Stunden nur "--" liefert, zeigt das
   Frontend weiterhin den alten Wert — ohne Hinweis auf das Alter.
2. **Tagesgrenze**: nach Mitternacht existiert die neue JSONL-Datei erst, sobald
   der Cron das nächste Mal gelaufen ist. Zwischen 00:00 und dem ersten
   erfolgreichen Fetch fällt die Live-Anzeige auf den Parquet-Fallback zurück.
3. **Keine Observability**: Fehler landen nur in `log.txt`, ohne Alarmierung und
   ohne sichtbaren Health-State.
4. **Cron-Takt**: 3h ist grob. GKD aktualisiert alle 15 Minuten; wir verschenken
   Frische.

### Plan

**1.1 Pipeline-Robustheit**

- Cron-Takt auf `*/15 * * *` reduzieren (15 min), mit Jitter um die Quelle zu
  schonen.
- Retry mit exponentiellem Backoff (3 Versuche) direkt in
  `fetch_latest_water_temperature()`.
- Zusätzliche Fallback-Quelle: GKD liefert auch eine CSV unter
  `.../messwerte.zrxp` oder `.../download` — prüfen und als zweiten Weg
  implementieren, falls das HTML-Scraping einmal bricht.
- Beim Speichern: "stale detection" — wenn der neueste Messwert älter als 2h
  ist, zusätzlich `stale: true` in den JSONL-Eintrag schreiben.

**1.2 Health-Status-Datei**

- Pipeline schreibt nach jedem Lauf `data/current/health.json`:
  ```json
  {
    "last_run": "2026-04-11T21:00:00+01:00",
    "water_level": { "ok": true, "latest_ts": "...", "age_minutes": 12 },
    "water_temperature": { "ok": true, "latest_ts": "...", "age_minutes": 30 }
  }
  ```
- Frontend liest `health.json` und zeigt im Landing-Status-Bereich einen kleinen
  Indikator ("aktualisiert vor X Min"), rot wenn > 6h alt.

**1.3 Live-Read über Tagesgrenzen**

- [liveData.ts](web/src/lib/liveData.ts) so umbauen, dass bei leerer heutiger
  Datei automatisch die gestrige gelesen wird (max 48h zurück).
- Damit verschwindet die "Mitternachts-Lücke" auch ohne Pipeline-Änderung.

**1.4 Logging**

- Strukturiertes Logging (eine Zeile pro Lauf als JSON) zusätzlich zum aktuellen
  Plaintext-Log, damit ein späterer Monitor-Job Fehlerquoten zählen kann.

### Akzeptanz

- Temperatur ist auf der Landing-Page nie älter als ~30 min, solange GKD liefert.
- Tagesgrenze produziert keine "--"-Anzeige mehr.
- Bei mehrstündigem GKD-Ausfall zeigt die UI "veraltet (vor Xh)".

---

## 2. Navigation: "Geschichte" → "Dahoam"

Reine i18n-Änderung, keine Routing-Änderung.

- [web/src/lib/i18n.tsx:10](web/src/lib/i18n.tsx#L10): `navStory: 'Geschichte'`
  → `'Dahoam'`
- Englisches Pendant im selben File: `'Story'` → `'Home'` (Dahoam ist
  bairisch für "zuhause"; in EN schlicht "Home").
- Schlüsselname `navStory` bleibt — kein Rename nötig, es ist nur ein Label.
- `AppLayout.tsx` braucht keine Änderung.
- CSS der aktiven NavLink bleibt; nur prüfen, ob längere Buchstabenkombination
  das Layout nicht sprengt.

### Akzeptanz

- Der Button im Header heißt in DE "Dahoam" und zeigt weiter auf `/`.

---

## 3. Video-Metadaten: EXIF/ffprobe-Auswertung + Infoblase

### Ist-Stand

- 15 Clips unter [web/public/videos/](web/public/videos/), hartkodiert in
  [web/src/components/VideoBackground.tsx:5-21](web/src/components/VideoBackground.tsx#L5-L21).
- Rohversionen unter `web/public/mp4_raw/` enthalten vollständige
  Container-Tags: `creation_time` und `location` (GPS als ISO-6709).
  Beispiel: `+48.1227+011.5681/` → 48.1227, 11.5681 (München).
- Die optimierten Clips unter `/videos/` haben diese Tags **nicht mehr** (vom
  optimize-Skript weggestrippt), deshalb muss die Auswertung auf den Raws
  passieren und das Ergebnis als JSON neben dem Clip liegen.

### Plan

**3.1 Build-time Metadaten-Extraktion (Pipeline)**

Neues Script [pipeline/extract_video_metadata.py](pipeline/extract_video_metadata.py):

- Iteriert `web/public/mp4_raw/*.mp4`.
- Nutzt `ffprobe -v error -print_format json -show_format` (bereits im
  Pipeline-Container verfügbar? Sonst in Dockerfile.pipeline nachziehen).
- Parst `creation_time` (UTC → Europe/Berlin) und `location` (ISO-6709
  Regex: `[+-]\d+\.?\d*[+-]\d+\.?\d*`).
- **Kopplung an Wasserdaten**: lädt die 15-min-Parquets aus
  `data/parquet/raw/station_16005701_water_{level,temperature}_{cm,c}.parquet`,
  sucht den nächsten Messwert (≤ 30 min Differenz) zum `creation_time`.
- Reverse-Geocoding: offline, da wir nur ein statisches Set von ~15 Clips
  haben — eine handgepflegte Mapping-Tabelle (lat,lon → Ortsname wie
  "Flaucher", "Reichenbachbrücke", "Wittelsbacherbrücke") im Script.
  Kein Netzwerk-Call, keine externe Abhängigkeit.
- Schreibt **eine** Datei `web/public/videos/metadata.json`:
  ```json
  {
    "20260103_155322.mp4": {
      "recordedAt": "2026-01-03T15:53:32+01:00",
      "location": { "lat": 48.1227, "lon": 11.5681, "name": "Flaucher" },
      "waterLevelCm": 142,
      "waterTemperatureC": 4.8,
      "season": "winter"
    },
    ...
  }
  ```
- Läuft im Cron einmal täglich **nachdem** die Parquets frisch sind — oder
  manuell per `make video-meta`. Da die Raws sich selten ändern, ist einmal
  täglich ausreichend.

**3.2 Frontend: Infoblase**

- [VideoBackground.tsx](web/src/components/VideoBackground.tsx) lädt
  `/videos/metadata.json` einmal beim Mount und merkt sich den Eintrag zum
  gerade abgespielten Clip.
- Neue Komponente `VideoInfoBubble.tsx` — kleiner Pill unten rechts über dem
  Video:
  ```
  📍 Flaucher · 3. Jan 2026 · Pegel 142 cm · 4,8 °C
  ```
- Sichtbar per default, per kleinem "i"-Toggle zuklappbar (State in
  `localStorage`, damit sich die Präferenz merkt).
- i18n-Keys: `videoInfoLocation`, `videoInfoRecorded`, `videoInfoLevel`,
  `videoInfoTemp`.
- Wenn `metadata.json` fehlt oder keinen Eintrag hat: Bubble unsichtbar, kein
  Error.

### Akzeptanz

- `metadata.json` existiert und enthält für jedes Video in `/videos/` einen
  Eintrag mit Datum, Location und Wasser-Snapshot.
- Auf der Landing-Page erscheint die Infoblase mit korrekten Werten.
- Wenn ein Video keine Raw-Entsprechung hat, fehlt lediglich die Bubble —
  kein Crash.

---

## 4. Kontextuelle Video-Auswahl (Saison / Wasserstand)

### Ziel

Die Auswahl bleibt zufällig, gewichtet sich aber so, dass Clips zur aktuellen
Situation bevorzugt werden. User hat explizit gesagt: "zufällig bleiben aber im
besten fall auch videos anzeigen die dem aktuellen wasserstand und / oder
jahreszeit entsprechen".

### Plan

**4.1 Scoring**

In `VideoBackground.tsx`, nachdem `metadata.json` geladen ist:

- **Saison-Match** (aus `recordedAt` → Monat):
  - winter: Dez–Feb, spring: Mär–Mai, summer: Jun–Aug, autumn: Sep–Nov.
  - gleiche Saison → +3.
- **Wasserstand-Match**:
  - Lade aktuellen Live-Wasserstand aus `liveData.ts` (bereits vorhanden).
  - Klassifiziere beides grob: low (<120 cm), normal (120–200), high (>200).
  - gleiche Klasse → +2; Nachbarklasse → +1.
- **Basis-Score**: jedes Video startet mit 1, damit auch nicht-matchende
  Clips eine Chance haben (Zufall bleibt echt).
- Gewichteter Zufall (reservoir / weighted pick).

**4.2 Session-Verhalten**

- Wie bisher: der in der Session gewählte Clip bleibt, bis die Seite neu
  aufgerufen wird. Das Scoring greift nur beim Neuladen, nicht beim Navigieren.
- Ein kleiner "Nächstes Video" Button (nur wenn Infoblase aufgeklappt) darf
  manuell neu würfeln — optional.

### Akzeptanz

- Im Winter mit normalem Pegel sieht man bevorzugt Winterclips, aber gelegentlich
  auch andere.
- Kein Video wird komplett ausgeschlossen.

---

## 5. Lokaler Photo-Curator (M:\Photos → Isar-Vorauswahl)

### Kontext

- Unter `M:\Photos\{2023,2024,2025,2026}` liegen ca. 25 GB private Aufnahmen
  (in WSL erreichbar als `/mnt/m/Photos/...`).
- Samsung-Aufnahmen haben zuverlässig GPS+Zeitstempel (stichprobenhaft geprüft:
  JPG via PIL, MP4 via ffprobe). Beispiel `2026/20260103_154258.jpg` →
  48°07'29.48"N 11°34'19.97"E, `DateTimeOriginal 2026:01:03 15:42:59`.
- Ziel: Tool, das **lokal** alle Assets scannt, diejenigen innerhalb von **30 m
  Luftlinie zur Isar** herausfiltert, Thumbnails erzeugt, und in einer
  lokalen SQLite-DB flaggt. Der User reviewt manuell; akzeptierte Assets
  werden nach `web/public/jpg_raw/` bzw. `web/public/mp4_raw/` kopiert und
  dienen anschließend als Eingabe für §3 (Metadaten-Extraktion) und das
  spätere Video/Bild-Archiv-Backend (§5).
- Das Tool lebt **außerhalb** der Web-Artefakte. Die DB, die Thumbs und der
  Index dürfen **nicht** deployt werden.

### Verzeichnis-Struktur (neu)

```
tools/photo-curator/
├── README.md
├── scan.py              # Phase 1: Index & Filter
├── thumbs.py            # Phase 2: Thumbnails
├── review.py            # Phase 3: lokaler Flask-Review-UI
├── promote.py           # Phase 4: Akzeptierte → jpg_raw/mp4_raw kopieren
├── isar-geometry.geojson
└── requirements.txt

imgsort/                 # bereits vorhanden; wird zum Arbeitsverzeichnis
├── curator.db           # SQLite (gitignored)
├── thumbs/              # 320px JPG Thumbnails (gitignored)
└── (bestehende JPGs bleiben als erstes manuelles Beispiel-Set erhalten)
```

`imgsort/curator.db` und `imgsort/thumbs/` in `.gitignore` nachziehen. Das
bestehende `imgsort/` ist laut `git status` ohnehin untracked — saubere
Baseline.

### Datenmodell (SQLite)

```sql
CREATE TABLE assets (
  id              INTEGER PRIMARY KEY,
  source_path     TEXT UNIQUE NOT NULL,   -- absoluter Pfad auf /mnt/m/...
  filename        TEXT NOT NULL,
  kind            TEXT NOT NULL,          -- 'photo' | 'video'
  taken_at        TEXT,                   -- ISO8601, Europe/Berlin
  lat             REAL,
  lon             REAL,
  distance_isar_m REAL,                   -- min-Luftlinie zur Isar-Polyline
  file_size       INTEGER,
  duration_s      REAL,                   -- nur videos
  width           INTEGER,
  height          INTEGER,
  sha1            TEXT,                   -- zur Dedup-Erkennung
  thumb_path      TEXT,                   -- relativ zu imgsort/thumbs/
  status          TEXT NOT NULL           -- 'new' | 'accepted' | 'rejected' | 'home-video'
                    DEFAULT 'new',
  tags            TEXT,                   -- comma-separated, frei
  notes           TEXT,
  scanned_at      TEXT NOT NULL,
  promoted_at     TEXT
);
CREATE INDEX idx_assets_status ON assets(status);
CREATE INDEX idx_assets_taken_at ON assets(taken_at);
CREATE INDEX idx_assets_distance ON assets(distance_isar_m);
```

`status = 'home-video'` ist eine Zusatz-Markierung, nicht `accepted` —
damit kann der User entscheiden: nur Archiv, oder auch als Hintergrundclip
auf der Landing tauglich.

### Isar-Geometrie

- Einmalig von Overpass API herunterladen:
  ```
  [out:json][timeout:60];
  way(around:0,48.08,11.55)["waterway"="river"]["name"="Isar"];
  (._;>;);
  out geom;
  ```
  Besser: Bounding Box für Großraum München:
  ```
  way["waterway"="river"]["name"="Isar"](48.05,11.40,48.30,11.75);
  out geom;
  ```
- Das Ergebnis als **GeoJSON LineString-Collection** nach
  `tools/photo-curator/isar-geometry.geojson` ablegen. Das File committen —
  es ist klein (~50 KB) und ändert sich nicht.
- Distanzberechnung Punkt → Polylinie:
  - Projektion in metrisches CRS (UTM 32N / EPSG:25832) via `pyproj`, dann
    euklidische Distanz zum nächsten Segment. Schneller und präziser als
    Haversine-pro-Segment, besonders bei 30 m Schwelle.
  - Alternativ: `shapely` (`LineString.distance(Point)` nach transform).
    `shapely + pyproj` ist die sauberste Variante — beides sind kleine
    Dependencies.

### Phase 1 — `scan.py`

**CLI**:
```
python scan.py --root /mnt/m/Photos/2026 --max 100 --threshold 30
python scan.py --root /mnt/m/Photos/2026 --all
```

**Verhalten**:
- Walk über `--root`, Dateien `.jpg .jpeg .mp4 .mov` (case-insensitive).
- `--max N`: hard cap für erste Testläufe (User explizit: "fangen auch erst
  mit einer kleinen Anzahl zum testen an").
- Pro Datei:
  - Falls `source_path` schon in `assets`: skip (außer `--rescan`).
  - EXIF/ffprobe → lat, lon, taken_at, width/height, duration.
  - Wenn kein GPS: Eintrag mit `distance_isar_m = NULL`, `status = 'new'`,
    **kein** Thumbnail. Solche Einträge taucht nicht in der Review auf,
    bleibt aber in der DB für Statistik.
  - Wenn GPS vorhanden: `distance_isar_m` berechnen. Nur wenn
    `distance_isar_m ≤ threshold` Insert mit `status='new'`. Darüber hinaus
    nichts speichern — sonst bläht die DB auf für irrelevante Assets.
  - SHA1 über die ersten 1 MB (schneller Dedup-Proxy; voller Hash wäre
    overkill für 25 GB).
- Progress-Output mit `tqdm`.
- Am Ende: Summary `scanned=X, with_gps=Y, near_isar=Z`.

**Testlauf-Strategie**:
1. Erster Durchlauf nur `--root /mnt/m/Photos/2026 --max 50`. Ergebnis
   manuell sichten: stimmen die Distanzen, stimmen die Zeitstempel?
2. Dann `--root /mnt/m/Photos/2026 --all`.
3. Dann die anderen Jahre.

### Phase 2 — `thumbs.py`

- Für alle `assets` mit `thumb_path IS NULL` und `distance_isar_m ≤ threshold`:
  - Photo: PIL resize auf max. 320 px lange Kante, JPEG q=75 → `imgsort/thumbs/<id>.jpg`.
  - Video: `ffmpeg -ss 00:00:01 -i <src> -frames:v 1 -vf scale=320:-1
    imgsort/thumbs/<id>.jpg`.
- `thumb_path = "<id>.jpg"` in die DB.
- Idempotent, überspringt bereits existierende Thumbs.
- Dauer: für ~500 near-Isar-Assets wenige Minuten.

### Phase 3 — `review.py` (lokaler Review-UI)

- Flask (oder Starlette) auf `127.0.0.1:5757`, nur localhost bind, keine Auth.
- Routes:
  - `GET /` → Grid aller Assets mit `status='new'`, sortiert nach `taken_at`.
    Jede Karte: Thumb + Datum + Distanz + Buttons "Accept / Reject /
    Home-Video / Tag…".
  - `GET /thumb/<id>.jpg` → aus `imgsort/thumbs/` ausliefern.
  - `GET /full/<id>` → Original-Asset streamen (für Vollansicht-Modal).
    Nur vom localhost aus, Pfad-Validierung gegen DB-Eintrag (kein
    Directory-Traversal).
  - `POST /status/<id>` → status + tags update.
  - `GET /accepted` → Liste der akzeptierten Assets mit "Promote"-Button.
- Keyboard-Shortcuts: `a` accept, `r` reject, `h` home-video, `j/k` nav.
- State bleibt nur in der DB — kein eigenes UI-State-File.

### Phase 4 — `promote.py`

- Kopiert akzeptierte Assets (`status IN ('accepted','home-video')` und
  `promoted_at IS NULL`) nach:
  - `web/public/jpg_raw/<filename>` für Fotos
  - `web/public/mp4_raw/<filename>` für Videos
- Setzt `promoted_at = now()`.
- **Kollisionen** (gleicher Dateiname existiert schon): Suffix `-1`, `-2`.
- Ruft **nicht** automatisch §3.1 (`extract_video_metadata.py`) auf — das
  bleibt ein separater Pipeline-Schritt. Damit bleibt das Curator-Tool
  strikt lokal und die Pipeline unabhängig.
- Optional Flag `--dry-run`, `--delete-after` (letzteres **nicht** für
  Testläufe).

### Dependencies (tools/photo-curator/requirements.txt)

```
Pillow>=10.0
pyproj>=3.6
shapely>=2.0
flask>=3.0
tqdm>=4.66
```

`ffmpeg`/`ffprobe` müssen system-seitig da sein (sind sie in WSL bereits).

### Security / Privacy

- Das Tool greift auf private Fotos zu und darf **nichts** davon ins Repo
  pushen. `.gitignore` entsprechend:
  ```
  imgsort/curator.db
  imgsort/thumbs/
  web/public/jpg_raw/
  ```
  `web/public/mp4_raw/` ist bereits Teil des Repos mit bewusst freigegebenen
  Clips — das bleibt so; `jpg_raw/` sollte denselben Freigabe-Workflow
  haben (committen nach manuellem Review).
- Review-UI bindet nur auf `127.0.0.1`, nie auf `0.0.0.0`.
- Kein externer API-Call im Betrieb (Overpass nur einmalig beim Aufsetzen).

### Akzeptanzkriterien

- `scan.py --root /mnt/m/Photos/2026 --max 50` läuft durch, produziert eine
  `curator.db` mit plausiblen Einträgen, inklusive korrekter Distanzen zur
  Isar.
- `thumbs.py` erzeugt Thumbs nur für Isar-nahe Assets.
- `review.py` zeigt das Grid lokal im Browser, Statuswechsel funktionieren.
- `promote.py` kopiert Assets in die Raw-Ordner, die anschließende
  Pipeline aus §3.1 erkennt sie und ergänzt `metadata.json`.

### Reihenfolge (innerhalb von §5)

1. Overpass-Download der Isar-Geometrie, Ergebnis manuell sichten (ist die
   Polyline vernünftig, hat sie Lücken?).
2. `scan.py` mit kleinem `--max` gegen `/mnt/m/Photos/2026`.
3. Ergebnisse manuell validieren (Distanz-Plausibilität).
4. `thumbs.py`.
5. `review.py`.
6. `promote.py`.
7. Erst dann die anderen Jahre `2023/2024/2025` scannen — 2025 zuerst, weil
   dort schon manuell ausgewählte Fotos in `imgsort/` liegen, die als
   Ground-Truth-Vergleich dienen.

---

## 6. Ausblick: Backend für Video- und Bild-Assets

Nur Skizze, noch keine Umsetzung — zur Orientierung für spätere Arbeit.

### Motivation

- Metadaten sollen editierbar sein (Ortsname manuell korrigieren, Tags
  ergänzen, Clips ein-/ausblenden).
- Aktuell liegt `metadata.json` unter `web/public/` und wird beim Build
  ausgeliefert — read-only für Endnutzer ist ok, aber ein Admin-Zugang fehlt.

### Vorschlag (nicht in diesem Durchlauf zu implementieren)

- Neuer Service `videos-api` (Node/Express oder Python/FastAPI, je nach
  Geschmack — FastAPI passt besser zum Pipeline-Stack).
- Persistenz: SQLite-Datei unter `data/videos.db` oder einfach eine
  versionierte `videos.yaml` im Repo.
- Endpoints:
  - `GET /api/videos` → Liste aller Clips mit Metadaten
  - `GET /api/videos/:id` → Einzeldaten
  - `POST /api/videos/:id` → Update (hinter Basic-Auth oder Netzwerksperre)
- Frontend holt `metadata.json` dann vom API statt vom statischen Pfad.
- Das pipeline-Script aus §3.1 wird zum Seeder: es füllt leere Einträge auf,
  überschreibt aber keine manuell gesetzten Felder.
- In NPM (nginx-proxy-manager) ein neues Proxy-Host-Forward auf
  `videos-api:8000` einrichten.

---

## Reihenfolge & Tracking

Empfohlene Commit-Reihenfolge (jeweils eigener Commit):

1. **Dahoam-Rename** (§2) — 1 Zeile i18n, risikofrei, sofort deploybar.
2. **liveData.ts Tagesgrenzen-Fix** (§1.3) — kleiner Frontend-Patch.
3. **Cron-Takt + Retry + health.json** (§1.1, §1.2) — Pipeline-Änderung.
4. **health.json im Frontend anzeigen** (§1.2) — UI-Indikator.
5. **extract_video_metadata.py + metadata.json** (§3.1).
6. **VideoInfoBubble-Komponente** (§3.2).
7. **Kontextuelle Video-Auswahl** (§4).
8. **Photo-Curator Phase 1–4** (§5) — parallel zu 5–7 möglich, unabhängig.
9. *(später)* Assets-API (§6).

Schritte 1–4 adressieren die Zuverlässigkeit, 5–7 das Video-Feature, 8 den
Content-Nachschub. Die Blöcke sind unabhängig und dürfen parallel gebaut werden.

## Entscheidungen zu den offenen Fragen

### Ortsnamen-Mapping (§3.1)

Vorgehen statt statischer Mapping-Tabelle aus dem Bauch heraus:

1. **Erst messen, dann benennen**: `extract_video_metadata.py` schreibt in
   Version 1 nur die rohen `lat/lon` + generisches `"Isar, München"` als
   Fallback.
2. **Cluster-basiert manuell labeln**: nach dem ersten Lauf über alle
   Raw-Videos (inkl. der später durch §5 dazugekommenen) erzeugt das Script
   zusätzlich `tools/photo-curator/locations.yaml` mit allen einzigartigen
   Koordinaten-Clustern (Rundung auf 3 Nachkommastellen ≈ 110 m). Der User
   editiert die YAML einmalig mit sprechenden Namen
   (`48.1227,11.5681: Flaucher`). Das Script liest die YAML bei
   Folgeläufen und bevorzugt manuelle Namen.
3. **Kandidaten für den initialen Durchlauf** (nur zur Orientierung, nicht
   committed) auf Basis der in §3 erkannten Cluster in den existierenden
   15 Clips: Flaucher, Wittelsbacherbrücke, Reichenbachbrücke,
   Museumsinsel, Maximiliansbrücke, Wehrsteg, Tivoli-Kraftwerk. Tatsächliche
   Zuordnung erfolgt gegen die echten Koordinaten nach dem ersten Lauf.

Damit vermeide ich, jetzt Namen zu erfinden, die zu den tatsächlichen GPS-
Punkten gar nicht passen.

### Pegel-Klassengrenzen (§4)

Nicht hardcoden — aus den Daten ableiten:

- Beim Build / Cron-Lauf aus dem 15-Min-Parquet die **Perzentile** 33/66 auf
  der kompletten Zeitreihe berechnen (oder auf den letzten 10 Jahren).
- Ergebnis in `data/parquet/station_meta.json` ergänzen:
  ```json
  "water_level_classes": { "low_max": 118, "high_min": 174 }
  ```
- Frontend liest diese Grenzen beim Init von `station_meta.json`. Kein Wert
  im Code — Grenzen passen sich automatisch an erweiterte Historie an.
- Saison-Klassen brauchen das nicht: Monat → fester Mapping.

### Backend-Stack (§6, später)

- **FastAPI** als Entscheidung — Gründe:
  - Gleicher Python-Stack wie `pipeline/`, gleicher Container-Workflow, kein
    neuer Toolchain-Zweig.
  - Die Pipeline liefert sowieso schon pandas/pyarrow-Daten; FastAPI kann
    die direkt ohne Bridge ausliefern.
  - Auto-OpenAPI-Schema ist für ein internes Admin-Panel praktisch.
- Node/Express käme nur in Frage, wenn das Frontend-Team das Backend
  mitbauen soll — derzeit nicht der Fall.

Entscheidung damit getroffen; §6 bleibt trotzdem Ausblick ohne Umsetzung in
dieser Iteration.

## Neue offene Fragen

- **Isar-Geometrie-Quelle**: OSM Overpass ist der pragmatische Weg, aber die
  Isar wird in OSM durch mehrere `way`-Segmente repräsentiert (Haupt- und
  Nebenarme, Floßlände-Kanal, Eisbach-Abzweigung). Soll der 30-m-Puffer
  **nur die Hauptisar** betreffen oder auch die Nebenarme (Floßlände,
  Auer Mühlbach, Isarkanal)? Für „Isar-Bilder" würde ich sagen: Hauptarm +
  Floßlände ja, Eisbach nein. Lass mich wissen, ob das passt.
- **30 m Schwelle**: sehr strikt. Bei Brückenaufnahmen (z.B. von der
  Reichenbachbrücke aus) stehst du gerne mal 10–20 m horizontal vom
  Hauptarm weg, aber auf einer Brücke. Das sollte mitkommen. 30 m scheint
  mir genau richtig. Wir können in Phase 1 mit `--threshold 30` starten und
  notfalls auf 50 m erhöhen — die DB ist dann eh schon da.
- **Jahre-Reihenfolge**: ich würde mit 2026 anfangen (kleinstes Volumen,
  frischer EXIF-Standard), dann rückwärts. OK?
