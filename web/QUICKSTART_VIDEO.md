# 🚀 Quick Start: Video Background

## In 3 Schritten zum Video-Hintergrund

### Schritt 1: ffmpeg installieren

```bash
sudo apt update && sudo apt install -y ffmpeg
```

### Schritt 2: Videos optimieren

```bash
cd /home/retroflex/monoroc/isarwasser/web
./optimize_videos.sh
```

**Was passiert:**
- Liest 15 Videos aus `public/mp4_raw/` (11-18 MB each)
- Optimiert sie auf ~2-5 MB
- Speichert in `public/videos/`
- **Gesamtgröße:** ~200MB → ~40-60MB (70-80% kleiner!)

### Schritt 3: Testen

```bash
npm run dev
```

➡️ Öffne http://localhost:5173

**Refresh mehrmals** um verschiedene Zufalls-Videos zu sehen!

---

## ✅ Was wurde bereits gemacht

- ✅ `VideoBackground.tsx` Component erstellt
- ✅ Landing Page angepasst
- ✅ CSS für Video-Hintergrund hinzugefügt
- ✅ Optimierungs-Script erstellt
- ✅ `.gitignore` konfiguriert
- ✅ Dokumentation erstellt

---

## 🎨 Features

- **Zufallsauswahl:** Jede Session bekommt ein zufälliges Video
- **Session-Persistence:** Gleiches Video während der Browsersession
- **Fullscreen:** Video füllt den gesamten Hintergrund
- **Smooth Fade-in:** Video blendet sanft ein wenn geladen
- **Overlay:** Dunkles Overlay für bessere Lesbarkeit
- **Backdrop Blur:** Cards haben leichten Blur-Effekt
- **Performance:** Optimierte Videos, non-blocking load

---

## 📊 Vorher/Nachher

### Vorher:
```
Landing Page: Statischer Gradient-Hintergrund
Größe: 0 MB
Ladezeit: Instant
```

### Nachher:
```
Landing Page: Dynamischer Video-Hintergrund
Videos: 15 verschiedene Isar-Aufnahmen
Größe: ~3-5 MB pro Video (optimiert)
Ladezeit: ~1-2s auf schneller Verbindung
```

---

## 🎥 Deine Videos

Du hast 15 Videos vom 03.01 - 23.01.2026:
- Verschiedene Tageszeiten
- Verschiedene Wetter-Situationen
- Verschiedene Perspektiven der Isar

Perfekt für einen abwechslungsreichen Hintergrund!

---

## 🔧 Troubleshooting

### "ffmpeg: command not found"
```bash
sudo apt install ffmpeg
```

### Script läuft nicht
```bash
chmod +x optimize_videos.sh
./optimize_videos.sh
```

### Videos zeigen nicht
1. DevTools Console öffnen (F12)
2. Fehler prüfen
3. Network Tab prüfen (laden die Videos?)

---

## 📝 Nächste Schritte

1. **Jetzt:** Videos optimieren & testen
2. **Später:** Eventuell weitere Videos hinzufügen
3. **Vor Go-Live:** Performance auf langsamer Verbindung testen

---

## 💡 Pro-Tipps

- **Session-Wechsel:** Inkognito-Tab öffnen = neues Video
- **Favorit festlegen:** In `VideoBackground.tsx` den `VIDEOS` Array anpassen
- **Weitere Videos:** Einfach in `mp4_raw` legen & Script erneut ausführen

Viel Spaß! 🌊
