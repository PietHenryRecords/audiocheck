from flask import Flask, render_template, request, send_file
import os
import re
import subprocess
import io
import csv

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Globale Variable für die Reports
reports_global = []

# Muster für Dateinamen: 001_Titel.mp3
FILENAME_PATTERN = re.compile(r'^\d{3}_.+\.mp3$')

def analyze_audio(filepath):
    try:
        cmd = [
            'ffmpeg', '-hide_banner', '-nostats', '-i', filepath,
            '-af', 'volumedetect',
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr

        mean_volume = None

        for line in output.splitlines():
            if "mean_volume:" in line:
                parts = line.split("mean_volume:")
                if len(parts) > 1:
                    mean_volume = float(parts[1].strip().replace(" dB", ""))
                    break

        if mean_volume is None:
            raise ValueError("Keine RMS-Daten (mean_volume) gefunden.")

        rms_ok = -24 <= mean_volume <= -18

        return {
            "Gemessene RMS (mean_volume, dB)": mean_volume,
            "RMS OK (zwischen -24 und -18 dB)": rms_ok
        }

    except Exception as e:
        return {
            "Fehler bei RMS-Messung": str(e)
        }

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', reports=reports_global)

@app.route('/upload', methods=['POST'])
def upload():
    global reports_global
    reports = []

    if 'files' not in request.files:
        return "Keine Dateien hochgeladen", 400

    files = request.files.getlist('files')

    for file in files:
        if file.filename.lower().endswith('.mp3') or file.filename.lower().endswith('.flac'):
            if not FILENAME_PATTERN.match(file.filename):
                reports.append(f"Fehler: Dateiname {file.filename} entspricht nicht dem Muster NNN_Titel.mp3.")
                continue

            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            analysis = None
            try:
                analysis = analyze_audio(filepath)
                reports.append({file.filename: analysis})
            except Exception as e:
                reports.append(f"Fehler bei {file.filename}: {str(e)}")

            try:
                if analysis is not None:
                    del analysis
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                print(f"Konnte Datei {filepath} nicht löschen: {e}")
        else:
            reports.append(f"Fehler: {file.filename} ist keine unterstützte Audiodatei.")

    reports_global = reports
    return render_template('index.html', reports=reports)

@app.route('/download_csv')
def download_csv():
    if not reports_global:
        return "Keine Daten zum Exportieren.", 400

    proxy = io.StringIO()
    writer = csv.writer(proxy)
    writer.writerow(['Dateiname', 'Gemessene RMS (mean_volume, dB)', 'Abweichung', 'RMS OK (zwischen -24 und -18 dB)'])

    for report in reports_global:
        if isinstance(report, dict):
            for filename, data in report.items():
                if 'Fehler bei RMS-Messung' in data:
                    writer.writerow([filename, data['Fehler bei RMS-Messung'], '', ''])
                else:
                    rms = data.get("Gemessene RMS (mean_volume, dB)", "")
                    rms_ok = "Ja" if data.get("RMS OK (zwischen -24 und -18 dB)", False) else "Nein"
                    if rms != "":
                        if rms > -18:
                            abweichung = f"{rms - (-18):.2f} dB zu laut"
                        elif rms < -24:
                            abweichung = f"{(-24) - rms:.2f} dB zu leise"
                        else:
                            abweichung = "Innerhalb der Toleranz"
                    else:
                        abweichung = ""

                    writer.writerow([filename, f"{rms:.2f}", abweichung, rms_ok])

    mem = io.BytesIO()
    mem.write(proxy.getvalue().encode('utf-8'))
    mem.seek(0)
    proxy.close()

    return send_file(mem,
                     as_attachment=True,
                     download_name='audio_check_results.csv',
                     mimetype='text/csv')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
