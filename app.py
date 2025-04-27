from flask import Flask, render_template, request, send_file
import os
import re
import subprocess
import io
import csv

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

reports_global = []
FILENAME_PATTERN = re.compile(r'^\d{3}_.*\.(mp3|wav)$', re.IGNORECASE)


def analyze_rms(filepath):
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
                parts = line.split('mean_volume:')[-1].strip()
                mean_volume = float(parts.split(' ')[0].replace('dB', ''))

        return mean_volume
    except Exception as e:
        print(f"Fehler bei RMS-Analyse: {e}")
        return None


def analyze_wav_details(filepath):
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=sample_rate,channels,bits_per_sample',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip().split('\n')

        if len(output) != 3:
            return None, None, None

        sample_rate = int(output[0])
        channels = int(output[1])
        bit_depth = int(output[2])

        return sample_rate, channels, bit_depth
    except Exception as e:
        print(f"Fehler bei WAV-Details-Analyse: {e}")
        return None, None, None


def generate_report(filename, extension, analysis):
    if extension == '.mp3':
        rms_value = analysis
        if rms_value is None:
            return make_error(filename, "Fehler bei RMS-Analyse")
        elif -24 <= rms_value <= -18:
            return make_success(filename, f"RMS: {rms_value:.2f} dB passt")
        else:
            return make_error(filename, f"RMS: {rms_value:.2f} dB außerhalb der Vorgaben")

    elif extension == '.wav':
        (sample_rate, channels, bit_depth, rms_value) = analysis
        if sample_rate != 44100:
            return make_error(filename, f"Sample Rate falsch: {sample_rate} Hz (erwartet: 44100 Hz)")
        if channels != 2:
            return make_error(filename, f"Kanalzahl falsch: {channels} (erwartet: Stereo)")
        if bit_depth != 16:
            return make_error(filename, f"Bit-Tiefe falsch: {bit_depth} Bit (erwartet: 16 Bit)")
        if rms_value is None:
            return make_error(filename, "Fehler bei RMS-Analyse")
        elif not (-24 <= rms_value <= -18):
            return make_error(filename, f"RMS: {rms_value:.2f} dB außerhalb der Vorgaben")
        else:
            return make_success(filename, f"Alle Prüfungen bestanden (RMS: {rms_value:.2f} dB)")

    else:
        return make_error(filename, "Unbekanntes Dateiformat")


def make_success(filename, details):
    return {
        'Datei': filename,
        'Prüfung': details,
        'Status': '✅ bestanden'
    }


def make_error(filename, details):
    return {
        'Datei': filename,
        'Prüfung': details,
        'Status': '❌ Fehler'
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    global reports_global
    reports_global = []

    if request.method == 'POST':
        files = request.files.getlist('files')
        for file in files:
            if file:
                filename = file.filename
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                name, extension = os.path.splitext(filename.lower())

                if extension == '.mp3':
                    rms = analyze_rms(filepath)
                    report = generate_report(filename, extension, rms)

                elif extension == '.wav':
                    sample_rate, channels, bit_depth = analyze_wav_details(filepath)
                    rms = analyze_rms(filepath)
                    report = generate_report(filename, extension, (sample_rate, channels, bit_depth, rms))

                else:
                    report = make_error(filename, "Nur MP3- und WAV-Dateien sind erlaubt")

                reports_global.append(report)

                os.remove(filepath)

    return render_template('index.html', reports=reports_global)


@app.route('/download', methods=['GET'])
def download_csv():
    global reports_global
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['Datei', 'Prüfung', 'Status'])
    writer.writeheader()
    for report in reports_global:
        writer.writerow(report)
    output.seek(0)

    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='Ergebnisse.csv')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
