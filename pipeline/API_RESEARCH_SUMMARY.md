# API Research Summary - München/Isar Pegeldaten

**Datum:** 25. Januar 2026  
**Station:** München / Isar (ID: 16005701)  
**Ziel:** Automatisiertes Abrufen aktueller Pegeldaten (alle 3 Stunden)

---

## 📊 Ergebnisse der Recherche

### ✅ Was funktioniert: HTML-Scraping

**Lösung:** Web-Scraping von hnd.bayern.de

- **URL:** https://www.hnd.bayern.de/pegel/isar/muenchen-16005701/tabelle?methode=wasserstand&setdiskr=15
- **Datenformat:** HTML-Tabelle mit 15-Minuten-Werten
- **Historische Daten:** ~7 Tage (641 Datenpunkte à 15 Minuten)
- **Zuverlässigkeit:** Stabil, gut scrapbar
- **Update-Frequenz:** Alle 15 Minuten

### ❌ Was NICHT verfügbar ist:

#### 1. PEGELONLINE REST-API
- **Status:** ❌ München/Isar nicht verfügbar
- **Grund:** PEGELONLINE deckt nur Bundeswasserstraßen ab
- **Isar München:** Unter bayerischer Landeshoheit (LfU Bayern)
- **Getestet:** ✅ (siehe `test_pegelonline.py`)

#### 2. Offizielle JSON/REST-APIs
Getestete Endpoints (alle 404):
- ❌ `hnd.bayern.de/webservices/daten.php`
- ❌ `hnd.bayern.de/webservices/messwerte.php`
- ❌ `hnd.bayern.de/api/pegel/{id}`
- ❌ `gkd.bayern.de/api/fluesse/wasserstand/{id}`
- ✅ `hnd.bayern.de/webservices/graphik.php` (nur PNG-Grafik, keine Daten)
- **Getestet:** ✅ (siehe `test_hnd_endpoints.py`)

#### 3. RSS/Atom Feeds
Getestete Feed-URLs (alle 404):
- ❌ `hnd.bayern.de/rss/pegel/{id}`
- ❌ `hnd.bayern.de/warnungen/rss`
- ❌ Keine Feed-Links in HTML-Meta-Tags gefunden
- **Getestet:** ✅ (siehe `test_rss_feeds.py`)

---

## 🛠️ Implementierte Lösung

### Scripts

1. **`fetch_isar_current.py`**
   - Holt alle verfügbaren Messwerte (641 Datenpunkte)
   - Speichert in `current_water_level.json`
   - Für manuelle Analyse/Debugging

2. **`fetch_and_store_isar.py`** ⭐ HAUPTSCRIPT
   - Holt nur den neuesten Wert
   - Speichert in JSONL-Format (tägliche Dateien)
   - Vermeidet Duplikate
   - Designed für Cron-Job (alle 3 Stunden)
   - Umfangreiches Logging

### Datenformat

**JSONL (JSON Lines):** Eine Messung pro Zeile

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

### Automatisierung

**Cron-Job Beispiel:**
```cron
# Alle 3 Stunden um :05 nach
5 */3 * * * cd /home/retroflex/monoroc/isarwasser/pipeline && /usr/bin/python3 fetch_and_store_isar.py >> /home/retroflex/monoroc/isarwasser/log.txt 2>&1
```

**Zeitpunkte:** 00:05, 03:05, 06:05, 09:05, 12:05, 15:05, 18:05, 21:05

---

## 📈 Vergleich der Optionen

| Option | Verfügbarkeit | Zuverlässigkeit | Aufwand | Empfehlung |
|--------|--------------|-----------------|---------|------------|
| PEGELONLINE API | ❌ Nicht verfügbar | N/A | N/A | ❌ |
| Offizielle API | ❌ Existiert nicht | N/A | N/A | ❌ |
| RSS Feeds | ❌ Nicht verfügbar | N/A | N/A | ❌ |
| HTML Scraping | ✅ Verfügbar | ⭐⭐⭐⭐ Gut | ⭐⭐ Mittel | ✅ **BESTE OPTION** |
| LfU kontaktieren | 🤔 Möglich | ⭐⭐⭐ ? | ⭐⭐⭐⭐ Hoch | 💡 Langfristig |

---

## 🎯 Empfehlungen

### Kurzfristig (JETZT):
1. ✅ **HTML-Scraping nutzen** (implementiert und funktioniert)
2. ✅ Cron-Job einrichten (siehe `CURRENT_DATA_README.md`)
3. ✅ Mit historischen Daten kombinieren

### Mittelfristig:
1. 📊 Daten in DuckDB integrieren
2. 🌐 Live-Daten in Web-App visualisieren
3. 📈 Monitoring für Scraping-Fehler einrichten

### Langfristig:
1. 📧 **LfU Bayern kontaktieren** (hnd@lfu.bayern.de)
   - Nach offizieller API fragen
   - Projekt vorstellen
   - Auf Bildungszweck hinweisen
2. 🤝 Falls API verfügbar wird: Migration von Scraping zu API

---

## ⚖️ Rechtliche Überlegungen

### ✅ Für Scraping:
- Daten sind öffentlich zugänglich (keine Paywall)
- Angemessenes Rate-Limiting (alle 3 Stunden)
- Identifiziert als "educational project"
- Keine kommerziellen Zwecke
- Respektiert robots.txt (falls vorhanden)

### ⚠️ Risiken:
- Website-Struktur könnte sich ändern (→ Scraper muss angepasst werden)
- LfU könnte Scraping explizit untersagen (→ dann API anfragen)
- Server-Last durch zu häufige Requests (→ durch 3h-Intervall vermieden)

---

## 📚 Dateien

- ✅ `test_pegelonline.py` - Testet PEGELONLINE API
- ✅ `test_hnd_endpoints.py` - Testet versteckte APIs
- ✅ `test_rss_feeds.py` - Testet RSS/Atom Feeds
- ✅ `fetch_isar_current.py` - Holt alle Werte (Debug)
- ✅ `fetch_and_store_isar.py` - Production Script für Cron
- ✅ `CURRENT_DATA_README.md` - Setup-Anleitung
- ✅ `API_RESEARCH_SUMMARY.md` - Dieses Dokument
- ✅ `requirements.txt` - Updated mit beautifulsoup4

---

## 🏁 Status

**✅ ABGESCHLOSSEN**

Die Recherche ist vollständig. Die einzige praktikable Lösung ist HTML-Scraping, und diese ist implementiert und getestet.

**Nächster Schritt:** Cron-Job einrichten und Datensammlung starten! 🚀
