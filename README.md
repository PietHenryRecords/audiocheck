# 🎧 AudioChecker – RMS-Fehlerprüfung für Sprecher

Dieses Tool ermöglicht es Sprechern und Autoren, ihre Audiobook-Dateien lokal auf Lautheit (RMS) zu prüfen und einen Fehlerbericht als PDF zu exportieren – einfach per Drag & Drop.

---

## ✅ Funktionen

- 🎚️ Lautheitsprüfung (RMS-Wert: -24 dB bis -18 dB)
- 📄 PDF-Fehlerbericht zum Download
- 📁 Mehrfach-Upload von MP3- und WAV-Dateien
- 🔒 100 % lokal im Browser – keine Datenübertragung
- 🌀 Lade-Spinner zur Anzeige der Verarbeitung
- 🖥️ Minimalistische Web-Oberfläche (Flask)

---

## 🚀 Projekt lokal starten

```bash
git clone https://github.com/PietHenryRecords/audiocheck.git
cd audiocheck
pip install -r requirements.txt
python app.py
