# Aktuelle Isar-Pegeldaten (Live Data Fetching)

## 🎯 Zusammenfassung

Da München/Isar **keine offizielle API** hat, nutzen wir **HTML-Scraping** von hnd.bayern.de um aktuelle Pegeldaten alle 3 Stunden abzurufen.

## 🔍 Recherche-Ergebnisse

### ❌ Was NICHT verfügbar ist:
- ❌ PEGELONLINE API (nur Bundeswasserstraßen, Isar in München nicht dabei)
- ❌ Offizielle JSON/REST API von hnd.bayern.de oder gkd.bayern.de
- ❌ RSS/Atom Feeds
- ❌ Versteckte API-Endpoints

### ✅ Was verfügbar ist:
- ✅ HTML-Tabellen auf hnd.bayern.de mit 15-Minuten-Werten
- ✅ Daten bis 7 Tage zurück verfügbar
- ✅ Zuverlässig scrapbar mit BeautifulSoup

## 🛠️ Setup

### 1. Dependencies installieren

```bash
cd /home/retroflex/monoroc/isarwasser/pipeline
pip3 install -r requirements.txt
```

### 2. Test-Scripts

#### Test PEGELONLINE (zeigt, dass München/Isar nicht verfügbar ist)
```bash
python3 test_pegelonline.py
```

#### Test versteckte Endpoints (zeigt, dass keine JSON-APIs existieren)
```bash
python3 test_hnd_endpoints.py
```

#### Test RSS Feeds (zeigt, dass keine Feeds existieren)
```bash
python3 test_rss_feeds.py
```

#### Fetch aktueller Werte (funktionierendes Script)
```bash
python3 fetch_isar_current.py
```

### 3. Automatisiertes Fetching

Das Script `fetch_and_store_isar.py`:
- Holt den neuesten Wasserstand von hnd.bayern.de
- Speichert ihn in JSONL-Format (ein JSON-Objekt pro Zeile)
- Vermeidet Duplikate
- Loggt alle Aktivitäten

#### Manual Test:
```bash
python3 fetch_and_store_isar.py
```

## ⏰ Automatisierung mit Cron

### Cron-Job einrichten (alle 3 Stunden)

1. Öffne crontab:
```bash
crontab -e
```

2. Füge diese Zeile hinzu (läuft alle 3 Stunden um :05 nach):
```cron
5 */3 * * * cd /home/retroflex/monoroc/isarwasser/pipeline && /usr/bin/python3 fetch_and_store_isar.py >> /home/retroflex/monoroc/isarwasser/log.txt 2>&1
```

**Zeitpunkte:** 00:05, 03:05, 06:05, 09:05, 12:05, 15:05, 18:05, 21:05

### Alternative: Systemd Timer

Für bessere Kontrolle kannst du einen systemd-Timer erstellen:

#### 1. Service-Datei: `/etc/systemd/system/isar-fetch.service`
```ini
[Unit]
Description=Fetch Isar Water Level Data
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=retroflex
WorkingDirectory=/home/retroflex/monoroc/isarwasser/pipeline
ExecStart=/usr/bin/python3 /home/retroflex/monoroc/isarwasser/pipeline/fetch_and_store_isar.py
StandardOutput=append:/home/retroflex/monoroc/isarwasser/log.txt
StandardError=append:/home/retroflex/monoroc/isarwasser/log.txt
```

#### 2. Timer-Datei: `/etc/systemd/system/isar-fetch.timer`
```ini
[Unit]
Description=Fetch Isar Water Level Data every 3 hours
Requires=isar-fetch.service

[Timer]
OnCalendar=*-*-* 00,03,06,09,12,15,18,21:05:00
Persistent=true

[Install]
WantedBy=timers.target
```

#### 3. Aktivieren:
```bash
sudo systemctl daemon-reload
sudo systemctl enable isar-fetch.timer
sudo systemctl start isar-fetch.timer

# Status prüfen
sudo systemctl status isar-fetch.timer
sudo systemctl list-timers | grep isar
```

## 📁 Datei-Struktur

```
isarwasser/
├── data/
│   └── current/
│       ├── water_level_2026-01-25.jsonl   # Tägliche JSONL-Dateien
│       ├── water_level_2026-01-26.jsonl
│       └── ...
├── pipeline/
│   ├── fetch_and_store_isar.py           # Hauptscript (für Cron)
│   ├── fetch_isar_current.py             # Voll-Script (alle Werte)
│   ├── test_pegelonline.py               # Test PEGELONLINE API
│   ├── test_hnd_endpoints.py             # Test versteckte APIs
│   └── test_rss_feeds.py                 # Test RSS feeds
└── log.txt                                # Haupt-Logfile
```

## 📊 Datenformat (JSONL)

Jede Zeile in den JSONL-Dateien ist ein JSON-Objekt:

```json
{
  "timestamp": "2026-01-25T16:00:00",
  "timestamp_unix": 1769353200,
  "date": "2026-01-25",
  "time": "16:00:00",
  "value_cm": 87,
  "unit": "cm",
  "station_id": "16005701",
  "station_name": "München / Isar",
  "source": "hnd.bayern.de",
  "fetched_at": "2026-01-25T16:18:19.230200"
}
```

## 📈 Daten verarbeiten

### Python lesen:
```python
import json

measurements = []
with open('data/current/water_level_2026-01-25.jsonl', 'r') as f:
    for line in f:
        measurements.append(json.loads(line))

# Latest value
latest = measurements[-1]
print(f"Latest: {latest['timestamp']} = {latest['value_cm']} cm")
```

### Zu Parquet konvertieren (für DuckDB/Analysis):
```python
import pandas as pd
import json

# Read all JSONL files
measurements = []
for jsonl_file in Path('data/current').glob('water_level_*.jsonl'):
    with open(jsonl_file, 'r') as f:
        for line in f:
            measurements.append(json.loads(line))

# Convert to DataFrame
df = pd.DataFrame(measurements)
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Save as Parquet
df.to_parquet('data/current/water_levels.parquet', index=False)
```

## 🔧 Troubleshooting

### Logs überprüfen:
```bash
tail -f /home/retroflex/monoroc/isarwasser/log.txt
```

### Letzte Cron-Ausführung:
```bash
grep "Isar water level" /home/retroflex/monoroc/isarwasser/log.txt | tail -5
```

### Manuell ausführen:
```bash
cd /home/retroflex/monoroc/isarwasser/pipeline
python3 fetch_and_store_isar.py
```

### Website-Struktur hat sich geändert?
Wenn das Scraping fehlschlägt, prüfe ob sich die HTML-Struktur geändert hat:
```bash
curl -s "https://www.hnd.bayern.de/pegel/isar/muenchen-16005701/tabelle?methode=wasserstand&setdiskr=15" | grep -A 5 "<table"
```

## 📧 Kontakt LfU Bayern

Falls du eine offizielle API möchtest, kontaktiere:
- **E-Mail**: hnd@lfu.bayern.de
- **Betreff**: "API-Zugang für Pegeldaten München/Isar (Station 16005701)"
- **Frage**: "Gibt es einen programmatischen Zugang (REST API, RSS Feed o.ä.) zu den Pegeldaten?"

## ⚖️ Rechtliches

- Die Daten von hnd.bayern.de sind öffentlich zugänglich
- Scraping mit angemessener Rate-Limiting (alle 3 Stunden) sollte okay sein
- User-Agent identifiziert das Projekt als "IsarWasser-Monitor/1.0 (educational project)"
- Bei Bedenken: LfU Bayern kontaktieren

## 🚀 Nächste Schritte

1. ✅ Scraper funktioniert
2. 🔄 Cron-Job einrichten
3. 📊 Daten mit historischen Daten kombinieren
4. 📈 In DuckDB integrieren
5. 🌐 In Web-App visualisieren
