from flask import Flask, render_template, request, send_file, redirect, url_for
import os
import subprocess
import io
import csv
import wave
import contextlib
import mutagen
from mutagen.wave import WAVE

def analyze_audio(filepath):
    # RMS-Messung
    try:
        cmd = [
            'ffmpeg', '-hide_banner', '-nostats', '-i', filepath,
            '-af', 'volumedetect', '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr

        mean_volume = None
        for line in output.splitlines():
            if "mean_volume:" in line:
                parts = line.split('mean_volume:')
                if len(parts) > 1:
                    mean_volume = parts[1].strip().replace(' dB', '')
                    break
        return float(mean_volume) if mean_volume else None
    except Exception as e:
        print(f"Fehler bei RMS-Analyse: {e}")
        return None

def check_wav_properties(filepath):
    try:
        with wave.open(filepath, 'rb') as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()

            # Bit-Tiefe berechnen
            bit_depth = sample_width * 8

            return {
                'channels': channels,
                'framerate': framerate,
                'bit_depth': bit_depth
            }
    except Exception as e:
        print(f"Fehler beim WAV-Check: {e}")
        return None

def check_mp3_properties(filepath):
    try:
        audio = mutagen.File(filepath)
        if audio.info:
            return {
                'channels': 2 if audio.info.mode == 'Joint stereo' or audio.info.mode == 'Stereo' else 1,
                'framerate': int(audio.info.sample_rate),
                'bit_depth': None  # MP3 hat keine Bit-Tiefe wie WAV
            }
    except Exception as e:
        print(f"Fehler beim MP3-Check: {e}")
        return None


app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
reports_global = []
ALLOWED_EXTENSIONS = {'mp3', 'wav'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    global reports_global
    if request.method == 'POST':
        reports_global = []

        if 'files' not in request.files:
            return redirect(request.url)

        files = request.files.getlist('files')

        for file in files:
            if file and allowed_file(file.filename):
                filepath = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(filepath)

                report = {'Datei': file.filename}

                extension = file.filename.rsplit('.', 1)[1].lower()

                if extension == 'wav':
                    props = check_wav_properties(filepath)
                else:
                    props = check_mp3_properties(filepath)

                if props:
                    status = []

                    # Sample Rate prüfen
                    if props['framerate'] != 44100:
                        status.append(f"Sample Rate falsch: {props['framerate']} Hz (erwartet: 44100 Hz)")

                    # Bit-Tiefe prüfen (nur bei WAV)
                    if extension == 'wav' and props['bit_depth'] != 16:
                        status.append(f"Bit-Tiefe falsch: {props['bit_depth']} Bit (erwartet: 16 Bit)")

                    # Stereo prüfen
                    if props['channels'] != 2:
                        status.append(f"Nicht Stereo: {props['channels']} Kanal(e) gefunden")

                    rms = analyze_audio(filepath)
                    if rms is not None:
                        report['RMS'] = f"{rms:.2f} dB"
                        if -24.0 <= rms <= -18.0:
                            report['RMS_OK'] = True
                        else:
                            report['RMS_OK'] = False
                            status.append(f"RMS falsch: {rms:.2f} dB (erwartet zwischen -24 dB und -18 dB)")
                    else:
                        report['RMS'] = "Keine RMS-Daten"
                        report['RMS_OK'] = False
                        status.append("RMS konnte nicht ermittelt werden")

                    if not status:
                        report['Status'] = 'passt'
                    else:
                        report['Status'] = 'Fehler'
                        report['Fehler'] = status

                reports_global.append(report)

                os.remove(filepath)

        return redirect(url_for('index'))

    return render_template('index.html', reports=reports_global)

@app.route('/download')
def download():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Datei', 'RMS', 'Status'])

    for report in reports_global:
        fehler_text = "; ".join(report.get('Fehler', [])) if report.get('Fehler') else "OK"
        writer.writerow([report['Datei'], report.get('RMS', 'N/A'), fehler_text])

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='audio_reports.csv'
    )

if __name__ == '__main__':
    app.run(debug=True)
