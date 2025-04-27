from flask import Flask, render_template, request, send_file
import os
import subprocess
import io
import csv
import re

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Globale Variable für die Reports
reports_global = []

# Muster für Dateinamen: 001_Titel.mp3 oder 001_Titel.wav
FILENAME_PATTERN = re.compile(r'^\d{3}_.*\.(mp3|wav)$')

def analyze_audio(filepath):
    cmd = [
        'ffmpeg', '-hide_banner', '-i', filepath,
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
                mean_volume = float(parts[1].strip().replace(' dB', ''))
                break

    return mean_volume

def analyze_format(filepath):
    cmd = [
        'ffprobe', '-hide_banner', '-v', 'error',
        '-select_streams', 'a:0',
        '-show_entries', 'stream=channels,sample_rate,bit_rate',
        '-of', 'default=noprint_wrappers=1:nokey=0', filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    info = {}

    for line in result.stdout.splitlines():
        if line.startswith('channels='):
            info['channels'] = int(line.replace('channels=', '').strip())
        if line.startswith('sample_rate='):
            info['sample_rate'] = int(line.replace('sample_rate=', '').strip())
        if line.startswith('bit_rate='):
            info['bit_rate'] = int(line.replace('bit_rate=', '').strip())

    return info

def process_file(file):
    errors = []
    filename = file.filename

    if not FILENAME_PATTERN.match(filename):
        errors.append("Dateiname entspricht nicht dem Muster (z.B. 001_Titel.mp3)")
        return {'Datei': filename, 'Fehler': errors}

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    extension = filename.lower().split('.')[-1]
    info = analyze_format(filepath)
    mean_volume = analyze_audio(filepath)

    if extension == 'wav':
        if info.get('sample_rate') != 44100:
            errors.append(f"Sample Rate falsch: {info.get('sample_rate')} Hz (erwartet: 44100 Hz)")
        if info.get('bit_rate'):
            bit_depth = int(int(info['bit_rate']) / info['sample_rate'] / info['channels'])
            if bit_depth != 16:
                errors.append(f"Bit-Tiefe falsch: {bit_depth} Bit (erwartet: 16 Bit)")
        if info.get('channels') != 2:
            errors.append(f"Nicht Stereo: {info.get('channels')} Kanal(e) gefunden")

    if extension == 'mp3':
        if info.get('channels') == 1:
            errors.append(f"Nicht Stereo: 1 Kanal gefunden (Mono)")

    if mean_volume is not None:
        if not (-24 <= mean_volume <= -18):
            errors.append(f"RMS falsch: {mean_volume:.2f} dB (erwartet zwischen -24 dB und -18 dB)")

    os.remove(filepath)
    return {'Datei': filename, 'Fehler': errors}

@app.route('/', methods=['GET', 'POST'])
def index():
    global reports_global
    success = False

    if request.method == 'POST':
        reports_global = []
        uploaded_files = request.files.getlist("files")

        for file in uploaded_files:
            if file:
                report = process_file(file)
                reports_global.append(report)

        success = True

    return render_template('index.html', reports=reports_global, success=success)

@app.route('/download', methods=['GET'])
def download():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Datei', 'Status', 'Fehler'])

    for report in reports_global:
        status = 'OK' if not report['Fehler'] else 'Fehler'
        fehler_text = '; '.join(report['Fehler']) if report['Fehler'] else ''
        writer.writerow([report['Datei'], status, fehler_text])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='ergebnisse.csv')

if __name__ == '__main__':
    app.run(debug=True)
